"""Tests for intermediate_validator.py — R4: Intermediate Validation"""
import pytest
from unittest.mock import MagicMock, patch
from engine.intermediate_validator import IntermediateValidator, StepValidation


# ── Initialization ───────────────────────────────────────────────────────────

class TestInitialization:
    def test_no_api_key(self):
        v = IntermediateValidator(api_key=None)
        assert v.is_available is False

    def test_with_api_key(self):
        with patch("engine.intermediate_validator.ImageValidator") as MockVal:
            v = IntermediateValidator(api_key="test_key")
            assert v.is_available is True

    def test_invalid_api_key(self):
        with patch("engine.intermediate_validator.ImageValidator", side_effect=Exception("bad key")):
            v = IntermediateValidator(api_key="bad_key")
            assert v.is_available is False


# ── Step Validation ──────────────────────────────────────────────────────────

class TestStepValidation:
    def test_skip_when_no_image(self):
        v = IntermediateValidator(api_key=None)
        result = v.validate_step({}, "test prompt")
        assert result.skipped is True
        assert "no_image_in_result" in result.issues

    def test_skip_when_no_api_key(self):
        v = IntermediateValidator(api_key=None)
        result = v.validate_step({"image_path": "/tmp/test.png"}, "test prompt")
        assert result.skipped is True
        assert "no_api_key" in result.issues

    def test_skip_non_generative_steps(self):
        v = IntermediateValidator(api_key=None)
        for action in ["upscale", "remove_bg", "face_restore"]:
            result = v.validate_step(
                {"image_path": "/tmp/test.png"}, "test", step_action=action
            )
            assert result.skipped is True

    def test_pass_when_image_path(self):
        with patch("engine.intermediate_validator.ImageValidator") as MockVal:
            mock_instance = MagicMock()
            mock_instance.validate.return_value = {
                "valid": True, "confidence": 0.9, "issues": []
            }
            MockVal.return_value = mock_instance

            v = IntermediateValidator(api_key="test_key")
            result = v.validate_step(
                {"image_path": "/tmp/test.png"}, "professional photo of sneaker"
            )
            assert result.valid is True
            assert result.confidence == 0.9
            assert result.should_continue is True
            assert result.skipped is False

    def test_fail_low_confidence(self):
        with patch("engine.intermediate_validator.ImageValidator") as MockVal:
            mock_instance = MagicMock()
            mock_instance.validate.return_value = {
                "valid": False, "confidence": 0.3, "issues": ["blurry", "wrong colors"]
            }
            MockVal.return_value = mock_instance

            v = IntermediateValidator(api_key="test_key")
            result = v.validate_step(
                {"image_path": "/tmp/test.png"}, "professional photo"
            )
            assert result.valid is False
            assert result.confidence == 0.3
            assert result.should_continue is False
            assert "blurry" in result.issues

    def test_custom_min_confidence(self):
        with patch("engine.intermediate_validator.ImageValidator") as MockVal:
            mock_instance = MagicMock()
            mock_instance.validate.return_value = {
                "valid": True, "confidence": 0.75, "issues": []
            }
            MockVal.return_value = mock_instance

            v = IntermediateValidator(api_key="test_key", min_confidence=0.8)
            result = v.validate_step(
                {"image_path": "/tmp/test.png"}, "test"
            )
            assert result.should_continue is False  # 0.75 < 0.8

    def test_error_handling_is_lenient(self):
        with patch("engine.intermediate_validator.ImageValidator") as MockVal:
            mock_instance = MagicMock()
            mock_instance.validate.side_effect = Exception("API timeout")
            MockVal.return_value = mock_instance

            v = IntermediateValidator(api_key="test_key")
            result = v.validate_step(
                {"image_path": "/tmp/test.png"}, "test"
            )
            # Error → lenient, don't abort pipeline
            assert result.should_continue is True
            assert result.valid is True


# ── Batch Validation ─────────────────────────────────────────────────────────

class TestBatchValidation:
    def test_batch(self):
        v = IntermediateValidator(api_key=None)
        results = v.validate_batch(
            [{"image_path": "a.png"}, {"image_path": "b.png"}],
            "test prompt",
        )
        assert len(results) == 2
        assert all(r.skipped for r in results)

    def test_batch_with_actions(self):
        v = IntermediateValidator(api_key=None)
        results = v.validate_batch(
            [{"image_path": "a.png"}, {"image_path": "b.png"}],
            "test",
            step_actions=["base_generation", "upscale"],
        )
        assert results[0].skipped is True  # no API key
        assert results[1].skipped is True  # upscale skipped


# ── StepValidation dataclass ─────────────────────────────────────────────────

class TestStepValidationDataclass:
    def test_defaults(self):
        sv = StepValidation()
        assert sv.valid is True
        assert sv.confidence == 1.0
        assert sv.should_continue is True
        assert sv.issues == []
        assert sv.skipped is False

    def test_to_dict(self):
        sv = StepValidation(valid=False, confidence=0.4, issues=["bad"])
        d = sv.to_dict()
        assert d["valid"] is False
        assert d["confidence"] == 0.4
        assert "bad" in d["issues"]
