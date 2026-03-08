#!/usr/bin/env python3
"""Basic contrast guardrail for brand background text readability."""

from __future__ import annotations


def hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    value = hex_color.strip().lstrip('#')
    if len(value) != 6:
        raise ValueError(f'Invalid hex color: {hex_color}')
    r = int(value[0:2], 16) / 255.0
    g = int(value[2:4], 16) / 255.0
    b = int(value[4:6], 16) / 255.0
    return r, g, b


def linearize(channel: float) -> float:
    if channel <= 0.04045:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def luminance(hex_color: str) -> float:
    r, g, b = hex_to_rgb(hex_color)
    return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)


def contrast_ratio(color_a: str, color_b: str) -> float:
    lum_a = luminance(color_a)
    lum_b = luminance(color_b)
    lighter = max(lum_a, lum_b)
    darker = min(lum_a, lum_b)
    return (lighter + 0.05) / (darker + 0.05)


def main() -> int:
    brand_bg = '#31b7ff'
    white_text = '#ffffff'
    dark_text = '#1a1a1a'

    white_ratio = contrast_ratio(brand_bg, white_text)
    dark_ratio = contrast_ratio(brand_bg, dark_text)

    # Header/footer has larger text and icon buttons, so 3.0:1 is baseline guardrail here.
    min_ratio = 3.0

    print(f'brand-bg vs white contrast: {white_ratio:.2f}')
    print(f'brand-bg vs dark contrast: {dark_ratio:.2f}')

    if max(white_ratio, dark_ratio) < min_ratio:
        print(f'Contrast check failed: both candidate text colors are below {min_ratio:.1f}:1')
        return 1

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
