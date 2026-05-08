"""Tests for encryption module."""

import pytest
from pathlib import Path
from src.security.encryption import (
    generate_key, encrypt_file, decrypt_file, encrypt_payload, _derive_key
)


class TestGenerateKey:
    def test_returns_string(self):
        key = generate_key()
        assert isinstance(key, str)

    def test_key_is_unique(self):
        k1 = generate_key()
        k2 = generate_key()
        assert k1 != k2

    def test_key_is_valid_fernet(self):
        from cryptography.fernet import Fernet
        key = generate_key()
        Fernet(key.encode())


class TestDeriveKey:
    def test_deterministic(self):
        k1 = _derive_key("my-password")
        k2 = _derive_key("my-password")
        assert k1 == k2

    def test_different_passwords_differ(self):
        k1 = _derive_key("password1")
        k2 = _derive_key("password2")
        assert k1 != k2

    def test_returns_bytes(self):
        k = _derive_key("test")
        assert isinstance(k, bytes)


class TestEncryptDecryptFile:
    def test_encrypt_creates_output_and_key_file(self, tmp_path):
        input_file = tmp_path / "plain.json"
        input_file.write_text('{"test": "data"}')
        output_file = tmp_path / "encrypted.enc"

        key = encrypt_file(str(input_file), str(output_file))

        assert output_file.exists()
        assert (tmp_path / "encrypted.enc.key").exists()
        assert isinstance(key, str)

    def test_encrypted_file_differs_from_original(self, tmp_path):
        input_file = tmp_path / "plain.txt"
        input_file.write_text("hello world")
        output_file = tmp_path / "enc.bin"

        encrypt_file(str(input_file), str(output_file))

        original = input_file.read_bytes()
        encrypted = output_file.read_bytes()
        assert original != encrypted

    def test_decrypt_restores_original(self, tmp_path):
        original_content = '{"scores": [1, 2, 3], "platform": "snowflake"}'
        input_file = tmp_path / "plain.json"
        input_file.write_text(original_content)
        enc_file = tmp_path / "enc.bin"
        dec_file = tmp_path / "decrypted.json"

        key = encrypt_file(str(input_file), str(enc_file))
        decrypt_file(str(enc_file), key, str(dec_file))

        assert dec_file.read_text() == original_content

    def test_encrypt_with_provided_key(self, tmp_path):
        from cryptography.fernet import Fernet
        my_key = Fernet.generate_key().decode()
        input_file = tmp_path / "data.txt"
        input_file.write_text("important data")
        output_file = tmp_path / "enc.bin"

        returned_key = encrypt_file(str(input_file), str(output_file), key=my_key)
        assert returned_key == my_key

    def test_wrong_key_raises(self, tmp_path):
        from cryptography.fernet import Fernet, InvalidToken
        input_file = tmp_path / "data.txt"
        input_file.write_text("secret")
        enc_file = tmp_path / "enc.bin"
        dec_file = tmp_path / "dec.txt"

        encrypt_file(str(input_file), str(enc_file))
        wrong_key = Fernet.generate_key().decode()

        with pytest.raises(Exception):
            decrypt_file(str(enc_file), wrong_key, str(dec_file))

    def test_decrypt_returns_output_path(self, tmp_path):
        input_file = tmp_path / "data.txt"
        input_file.write_text("test data")
        enc_file = tmp_path / "enc.bin"
        dec_file = tmp_path / "dec.txt"

        key = encrypt_file(str(input_file), str(enc_file))
        result = decrypt_file(str(enc_file), key, str(dec_file))
        assert result == str(dec_file)


class TestEncryptPayload:
    def test_encrypt_payload_convenience(self, tmp_path):
        json_file = tmp_path / "payload.json"
        json_file.write_text('{"platform": "test"}')
        enc_file = tmp_path / "payload.enc"

        key = encrypt_payload(str(json_file), str(enc_file))

        assert enc_file.exists()
        assert isinstance(key, str)

    def test_encrypt_payload_recoverable(self, tmp_path):
        content = '{"scores": {"snowflake": []}}'
        json_file = tmp_path / "payload.json"
        json_file.write_text(content)
        enc_file = tmp_path / "payload.enc"
        dec_file = tmp_path / "recovered.json"

        key = encrypt_payload(str(json_file), str(enc_file))
        decrypt_file(str(enc_file), key, str(dec_file))
        assert dec_file.read_text() == content
