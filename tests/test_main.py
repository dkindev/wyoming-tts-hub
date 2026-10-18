import os
import signal
import socket
import subprocess
import sys
import time
import tomllib
import unittest.mock
from importlib.metadata import entry_points
from pathlib import Path

import pytest
from openai import AsyncOpenAI
from setuptools import find_packages
from wyoming.event import read_event, write_event
from wyoming.info import Describe, Info

from src import __metadata__
from src import main as main_module
from src.config import (
    NormalizationPrompt,
    NormalizationSettings,
    OpenAiSettings,
    Settings,
    TextFormatNormalizationSettings,
)
from src.main import create_openai_client, setup_backend, warn_unreachable_prompts
from tests.helpers import FakeDataStorage, make_model_info

REPO_ROOT = Path(__file__).resolve().parent.parent
"""The checkout, for the packaging and Dockerfile claims made about it."""


@pytest.fixture
def usable_settings():
    """OpenAiSettings complete enough for create_openai_client to build a client."""
    return OpenAiSettings(base_url="http://localhost:8080/v1", api_key="key")


class TestSetupBackend:
    def test_torch_backend_applies_thread_settings(self, monkeypatch):
        """The torch backend pushes the configured thread counts into torch."""
        monkeypatch.setenv("TTS_TORCH__NUM_THREADS", "3")
        monkeypatch.setenv("TTS_TORCH__NUM_INTEROP_THREADS", "2")
        monkeypatch.setenv("TTS_TORCH__FLUSH_DENORMAL", "false")
        settings = Settings()

        with (
            unittest.mock.patch("torch.set_num_threads") as set_num_threads,
            unittest.mock.patch("torch.set_num_interop_threads") as set_interop,
            unittest.mock.patch("torch.set_flush_denormal") as flush_denormal,
        ):
            setup_backend(settings)

        set_num_threads.assert_called_once_with(3)
        set_interop.assert_called_once_with(2)
        flush_denormal.assert_not_called()

    def test_torch_backend_applies_flush_denormal_when_enabled(self, monkeypatch):
        """flush_denormal is only pushed when the setting asks for it."""
        monkeypatch.setenv("TTS_TORCH__FLUSH_DENORMAL", "true")
        settings = Settings()

        with (
            unittest.mock.patch("torch.set_num_threads"),
            unittest.mock.patch("torch.set_num_interop_threads"),
            unittest.mock.patch("torch.set_flush_denormal") as flush_denormal,
        ):
            setup_backend(settings)

        flush_denormal.assert_called_once_with(True)


class TestCreateOpenAiClient:
    def test_no_settings_returns_none(self):
        """Absent normalization settings mean no client."""
        assert create_openai_client(None) is None

    def test_missing_base_url_returns_none(self, usable_settings):
        """Without a base_url there is nothing to point the client at."""
        settings = usable_settings.model_copy(update={"base_url": ""})

        assert create_openai_client(settings) is None

    def test_missing_api_key_returns_none(self, usable_settings):
        """Without an api_key the client is not constructed."""
        settings = usable_settings.model_copy(update={"api_key": ""})

        assert create_openai_client(settings) is None

    def test_complete_settings_build_a_client(self, usable_settings):
        """A fully configured settings object yields an AsyncOpenAI pointed at base_url."""
        client = create_openai_client(usable_settings)

        assert isinstance(client, AsyncOpenAI)
        assert client.base_url == f"{usable_settings.base_url}/"


class TestWarnUnreachablePrompts:
    """An unreachable prompt is reported at startup, and never blocks the server."""

    def storage(self, *languages):
        return FakeDataStorage(models=[make_model_info(languages=list(languages))])

    def test_an_unreachable_prompt_is_reported(self):
        settings = NormalizationSettings(
            text=TextFormatNormalizationSettings(
                prompts={"ru_RU": NormalizationPrompt(text="t", model="m")}
            )
        )

        with unittest.mock.patch("src.main.logger.warning") as warning:
            warn_unreachable_prompts(settings, self.storage("ru"))

        warning.assert_called_once()
        assert "ru_RU" in warning.call_args.kwargs["languages"]

    def test_a_reachable_prompt_is_not_reported(self):
        settings = NormalizationSettings(
            text=TextFormatNormalizationSettings(
                prompts={"ru": NormalizationPrompt(text="t", model="m")}
            )
        )

        with unittest.mock.patch("src.main.logger.warning") as warning:
            warn_unreachable_prompts(settings, self.storage("ru"))

        warning.assert_not_called()

    def test_reporting_does_not_raise(self):
        """The server starts either way: an inert prompt is not a startup failure."""
        settings = NormalizationSettings(
            text=TextFormatNormalizationSettings(
                prompts={"ru_RU": NormalizationPrompt(text="t", model="m")}
            )
        )

        assert warn_unreachable_prompts(settings, self.storage("ru")) is None


COMMAND = "silero-server"
"""The command the distribution installs, named for the distribution."""

FREE_PORT_WAIT = 30.0
"""How long to wait for the server to bind before calling it a failure."""


def write_server_files(directory: Path, port: int) -> Path:
    """Write a config and data file that start a server without touching the network.

    No Model Info asks to be warmed up, so booting loads no engine and downloads
    nothing — the boot under test is the command, not the model.
    """
    data_yml = directory / "data.yml"
    data_yml.write_text(
        "models:\n"
        "  v5_5_ru:\n"
        "    engine_type: silero\n"
        "    languages: [ru]\n"
        "    voices:\n"
        "      - name: aidar\n"
    )
    config_yml = directory / "config.yml"
    config_yml.write_text(
        f"active_models: [v5_5_ru]\n"
        f"uri: tcp://127.0.0.1:{port}\n"
        f'zeroconf: ""\n'
        f"data_yml_path: {data_yml}\n"
        f"models_dir: {directory / 'models'}\n"
    )
    return config_yml


def reserve_port() -> int:
    """Ask the OS for a port nobody is using, and hand the number over."""
    reservation = socket.socket()
    reservation.bind(("127.0.0.1", 0))
    port = reservation.getsockname()[1]
    reservation.close()
    return port


def installed_command():
    """The console script this distribution installed, or None if it installed none."""
    entries = list(entry_points(group="console_scripts", name=COMMAND))
    return entries[0] if entries else None


def subprocess_env(**overrides) -> dict[str, str]:
    """The environment to start the command in, with no settings left over.

    The suite runs hermetically with a per-test `TTS_CONFIG_PATH` pointing at a
    generated config; a subprocess would inherit it and serve that instead of the one
    under test. An empty value is not enough — the setting is read as a path.
    """
    inherited = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith(Settings.model_config["env_prefix"])
        and name not in ("OPENAI_API_KEY", "OPENAI_BASE_URL")
    }

    return {**inherited, **overrides}


def command_path() -> Path:
    """The command as it sits on the path beside the running interpreter."""
    return Path(sys.executable).parent / COMMAND


class RunningServer:
    """The command started as a real process, waited for until it serves."""

    def __init__(self, arguments, cwd, **env):
        self._process = subprocess.Popen(
            [str(command_path()), *arguments],
            cwd=cwd,
            env=subprocess_env(**env),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self.output = ""

    def output_so_far(self) -> str:
        """Whatever the server has written, without blocking on it."""
        return self.output

    def wait_until_serving(self, port: int):
        """Block until the server answers on its port, or fail with its own words."""
        deadline = time.monotonic() + FREE_PORT_WAIT
        while time.monotonic() < deadline:
            exit_code = self._process.poll()
            assert exit_code is None, f"the server exited ({exit_code}):\n{self._read_output()}"
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    return
            except OSError:
                time.sleep(0.1)

        pytest.fail(f"the server never bound its port:\n{self._read_output()}")

    def describe(self, port: int) -> Info:
        """Ask the server what it offers, the way a client does on connecting.

        The writer is passed explicitly: wyoming sends to stdout when given none, which
        would print the request here instead of sending it.
        """
        with socket.create_connection(("127.0.0.1", port), timeout=10) as connection:
            writer = connection.makefile("wb")
            write_event(Describe().event(), writer)
            writer.flush()

            return Info.from_event(read_event(connection.makefile("rb")))

    def interrupt(self) -> int:
        """Send the signal Ctrl-C sends, and return how the server left."""
        self._process.send_signal(signal.SIGINT)
        return self._process.wait(timeout=FREE_PORT_WAIT)

    def stop(self):
        if self._process.poll() is None:
            self._process.kill()
            self._process.wait(timeout=10)

    def _read_output(self) -> str:
        if self.output or self._process.stdout is None:
            return self.output

        self.output = self._process.stdout.read()
        return self.output


class TestConsoleScript:
    """The distribution ships a command, rather than only a module to invoke."""

    def test_the_distribution_provides_the_command(self):
        """Reading the installed metadata is the only way to know what it ships.

        Declaring it in pyproject.toml is not enough — until the distribution is
        reinstalled, nothing is on the path, which is exactly the state a reader is in
        when they follow the documentation and get "no such file".
        """
        command = installed_command()

        assert command is not None, f"{COMMAND} is not installed; reinstall the distribution"
        assert command.load() is main_module.run

    def test_the_command_starts_the_server(self, monkeypatch):
        """Loading the command gives something that runs the server."""
        started = []

        async def fake_main():
            started.append(True)

        monkeypatch.setattr(main_module, "main", fake_main)

        installed_command().load()()

        assert started == [True]

    def test_the_command_runs_with_no_arguments(self, tmp_path):
        """Bare, from a directory, it reads the configuration sitting beside it.

        No flags and no environment: this is the reader who followed the Quick Start
        and typed the command. What it must not do is depend on being inside the source
        tree, which is what the module path used to require.
        """
        port = reserve_port()
        write_server_files(tmp_path, port)
        server = RunningServer([], cwd=tmp_path)

        try:
            server.wait_until_serving(port)
        finally:
            server.stop()

    def test_the_command_serves_the_voices_it_declares(self, tmp_path):
        """Reachable is not enough — the port answers the Wyoming protocol."""
        port = reserve_port()
        config_yml = write_server_files(tmp_path, port)
        server = RunningServer(["--config", str(config_yml)], cwd=tmp_path)

        try:
            server.wait_until_serving(port)
            info = server.describe(port)
        finally:
            server.stop()

        assert [voice.name for program in info.tts for voice in program.voices] == ["v5_5_ru-aidar"]

    def test_the_command_stops_cleanly_on_interrupt(self, tmp_path):
        """Ctrl-C is an ordinary way to stop, not a traceback.

        Signalled rather than raised: the server installs its own handler and cancels
        the running task, so an injected KeyboardInterrupt would prove nothing about
        the path a real Ctrl-C takes.
        """
        port = reserve_port()
        config_yml = write_server_files(tmp_path, port)
        server = RunningServer(["--config", str(config_yml)], cwd=tmp_path)

        try:
            server.wait_until_serving(port)
            assert server.interrupt() == 0
        finally:
            server.stop()

        assert "Traceback" not in server.output_so_far()

    def test_the_image_runs_the_same_command(self):
        """The image's default command is the one the distribution installs."""
        dockerfile = (REPO_ROOT / "Dockerfile").read_text()

        assert f'CMD ["{COMMAND}"]' in dockerfile

    def test_the_wheel_ships_every_subpackage_of_src(self):
        """A wheel naming only the top package installs code that cannot import itself.

        The command's first import is `src.main`, which imports `src.tts` — so a wheel
        that left the subpackages out ships a command that fails on start. Narrowing
        the include pattern is the way that would happen again.
        """
        packaging = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())["tool"]["setuptools"]

        declared_setting = packaging.get("packages")
        if isinstance(declared_setting, list):
            declared = set(declared_setting)
        elif declared_setting is not None:
            declared = set(
                find_packages(where=REPO_ROOT, include=declared_setting["find"]["include"])
            )
        else:
            pytest.fail("the distribution declares no packages at all")

        assert declared == set(find_packages(where=REPO_ROOT, include=["src*"]))


def pyproject() -> dict:
    """The packaging metadata as it is written in the source."""
    return tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())


class TestPackageMetadata:
    """What the distribution says about itself, which clients read over the protocol."""

    @staticmethod
    def project() -> dict:
        return pyproject()["project"]

    def test_the_installed_distribution_is_the_one_written(self):
        """The served description is the *installed* summary, not this file's.

        The two are read from different places — one from pyproject.toml, one from the
        installed distribution's metadata — and nothing else ties them together, so
        editing the summary and not reinstalling would leave a client being told
        something the project no longer says.
        """
        assert __metadata__["summary"] == pyproject()["project"]["description"]

    def test_the_summary_describes_a_tts_engine_hub(self):
        """The summary is what a client is told the server is.

        It used to say the server wraps the Silero TTS engine, which described one
        engine family as though it were the whole of the project.
        """
        summary = self.project()["description"]

        assert "TTS Engine Hub" in summary
        assert "TTS Engines" in summary
        assert "wraps the Silero" not in summary

    def test_the_keywords_name_the_hub_and_the_engine_family_it_aggregates(self):
        """Search terms a reader reaches for, naming what the project actually is."""
        keywords = set(self.project()["keywords"])

        assert "tts-engine-hub" in keywords
        assert "silero" in keywords
