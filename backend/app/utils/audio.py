"""Audio helpers."""
from app.core.constants import DEFAULT_CHANNELS, DEFAULT_SAMPLE_RATE


def pcm_duration_ms(num_bytes: int, sample_rate: int = DEFAULT_SAMPLE_RATE, channels: int = DEFAULT_CHANNELS, sample_width: int = 2) -> int:
    if sample_rate <= 0 or channels <= 0 or sample_width <= 0:
        return 0
    frames = num_bytes / (channels * sample_width)
    return int((frames / sample_rate) * 1000)
