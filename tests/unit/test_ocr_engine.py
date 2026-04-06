import os
import sys
import types

from japim.ocr.engine import OCREngine


class _FakeResult:
    def __init__(self, payload):
        self.json = payload


def test_ocr_engine_falls_back_to_cpu_when_gpu_architecture_is_unsupported(monkeypatch):
    calls: list[str] = []

    class FakePaddleOCR:
        def __init__(
            self,
            *,
            lang,
            use_doc_orientation_classify,
            use_doc_unwarping,
            use_textline_orientation,
            device,
            text_detection_model_dir=None,
            text_recognition_model_dir=None,
            textline_orientation_model_dir=None,
            show_log=False,
            ocr_version=None,
        ):
            calls.append(device)
            if device != "cpu":
                raise RuntimeError("Unsupported GPU architecture")

        def predict(self, image_path):
            return [
                _FakeResult(
                    {
                        "res": {
                            "rec_texts": ["EMAIL abcdef@example.com"],
                            "rec_scores": [0.99],
                            "rec_boxes": [[10, 20, 110, 60]],
                        }
                    }
                )
            ]

    monkeypatch.setitem(sys.modules, "paddleocr", types.SimpleNamespace(PaddleOCR=FakePaddleOCR))

    engine = OCREngine(
        backend="paddle",
        lang="korean",
        use_angle_cls=True,
        confidence_threshold=0.1,
        use_gpu=True,
        device="gpu:0",
        show_log=False,
    )

    tokens = engine.recognize("dummy.png", page_no=1)

    assert [token.text for token in tokens] == ["EMAIL abcdef@example.com"]
    assert calls == ["gpu:0", "cpu"]
    assert engine.use_gpu is False
    assert engine.device == "cpu"


def test_ocr_engine_applies_gpu_runtime_limits_and_kwargs(monkeypatch):
    captured_kwargs = {}

    class FakePaddleModule:
        class device:
            @staticmethod
            def is_compiled_with_cuda():
                return True

            class cuda:
                @staticmethod
                def device_count():
                    return 1

    class FakePaddleOCR:
        def __init__(
            self,
            *,
            lang,
            use_doc_orientation_classify,
            use_doc_unwarping,
            use_textline_orientation,
            device,
            text_detection_model_name=None,
            text_detection_model_dir=None,
            textline_orientation_model_name=None,
            textline_orientation_model_dir=None,
            textline_orientation_batch_size=None,
            text_recognition_model_name=None,
            text_recognition_model_dir=None,
            text_recognition_batch_size=None,
            text_det_limit_side_len=None,
            text_det_limit_type=None,
            show_log=False,
            ocr_version=None,
        ):
            captured_kwargs.update(
                {
                    "device": device,
                    "text_detection_model_name": text_detection_model_name,
                    "text_recognition_model_name": text_recognition_model_name,
                    "textline_orientation_model_name": textline_orientation_model_name,
                    "text_det_limit_side_len": text_det_limit_side_len,
                    "text_det_limit_type": text_det_limit_type,
                    "textline_orientation_batch_size": textline_orientation_batch_size,
                    "text_recognition_batch_size": text_recognition_batch_size,
                }
            )

        def predict(self, image_path):
            return [
                _FakeResult(
                    {
                        "res": {
                            "rec_texts": ["EMAIL abcdef@example.com"],
                            "rec_scores": [0.99],
                            "rec_boxes": [[10, 20, 110, 60]],
                        }
                    }
                )
            ]

    monkeypatch.setitem(sys.modules, "paddleocr", types.SimpleNamespace(PaddleOCR=FakePaddleOCR))
    monkeypatch.setitem(sys.modules, "paddle", FakePaddleModule)
    monkeypatch.delenv("FLAGS_allocator_strategy", raising=False)
    monkeypatch.delenv("FLAGS_fraction_of_gpu_memory_to_use", raising=False)

    engine = OCREngine(
        backend="paddle",
        lang="korean",
        use_angle_cls=False,
        confidence_threshold=0.1,
        use_gpu=True,
        device="gpu:0",
        text_detection_model_name="PP-OCRv5_mobile_det",
        text_recognition_model_name="korean_PP-OCRv5_mobile_rec",
        textline_orientation_model_name="PP-LCNet_x0_25_textline_ori",
        text_det_limit_side_len=960,
        text_det_limit_type="max",
        textline_orientation_batch_size=1,
        text_recognition_batch_size=1,
        gpu_allocator_strategy="auto_growth",
        fraction_of_gpu_memory_to_use=0.1,
        show_log=False,
    )

    tokens = engine.recognize("dummy.png", page_no=1)

    assert [token.text for token in tokens] == ["EMAIL abcdef@example.com"]
    assert captured_kwargs["device"] == "gpu:0"
    assert captured_kwargs["text_detection_model_name"] == "PP-OCRv5_mobile_det"
    assert captured_kwargs["text_recognition_model_name"] == "korean_PP-OCRv5_mobile_rec"
    assert captured_kwargs["text_det_limit_side_len"] == 960
    assert captured_kwargs["text_det_limit_type"] == "max"
    assert captured_kwargs["text_recognition_batch_size"] == 1
    assert os.environ["FLAGS_allocator_strategy"] == "auto_growth"
    assert os.environ["FLAGS_fraction_of_gpu_memory_to_use"] == "0.1"
