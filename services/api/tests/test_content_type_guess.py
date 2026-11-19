"""Listing content types come from the key's extension, independent of the host's mime.types."""

import mimetypes

from app.repo import b2_client


def test_ogg_recordings_list_as_audio_even_without_system_mime_types(monkeypatch):
    # The slim api image has no /etc/mime.types, so mimetypes knows no `.ogg`.
    monkeypatch.setattr(mimetypes, "guess_type", lambda _key: (None, None))

    assert b2_client._guess_content_type("sessions/2026-11-19/s-1/recording.ogg") == "audio/ogg"
    assert b2_client._guess_content_type("sessions/2026-11-19/s-1/RECORDING.OGG") == "audio/ogg"
    assert b2_client._guess_content_type("no-extension") == "application/octet-stream"
