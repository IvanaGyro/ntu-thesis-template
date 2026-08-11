#!/usr/bin/env python3
"""Regenerate the four example plots used by contents/chapter02.tex.

The PDFs are committed, so neither Overleaf nor a plain latexmk build needs
Python. Run this only to refresh or restyle them:

    pixi run python scripts/make_example_figures.py

Every plot is drawn from a fixed random seed, so re-running reproduces the
committed files. Nothing here is wired into `pixi run build` on purpose.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402  (backend must be set first)


FIGURES_DIR = Path(__file__).resolve().parents[1] / "figures"
SEED = 20260811

# The thesis body is set in a Times-like serif at 12pt. Matching the figures to
# it keeps captions and axis labels from looking like they came from a
# different document. DejaVu Serif is the fallback when no Times clone is
# installed; it is metrically different but still a serif.
plt.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["Nimbus Roman", "TeX Gyre Termes", "DejaVu Serif"],
        "font.size": 9,
        "axes.titlesize": 10,
        "axes.grid": True,
        "grid.alpha": 0.3,
        "grid.linewidth": 0.5,
        "axes.axisbelow": True,
        "figure.constrained_layout.use": True,
        "savefig.transparent": True,
        # Type 42 embeds TrueType outlines rather than Type 3 bitmapped glyphs,
        # so the text in the figures stays selectable and searchable in the PDF.
        "pdf.fonttype": 42,
    }
)


def save(fig: plt.Figure, name: str) -> None:
    path = FIGURES_DIR / name
    # Without this, matplotlib stamps the current time into the PDF and every
    # run rewrites all four files, showing up as a dirty working tree even
    # when the plots are unchanged. Dropping CreationDate makes the output a
    # pure function of the seed.
    fig.savefig(path, format="pdf", metadata={"CreationDate": None})
    plt.close(fig)
    print(f"wrote {path.relative_to(FIGURES_DIR.parent)}")


def histogram(rng: np.random.Generator) -> None:
    """Histogram of a sample with the fitted normal density on top."""
    sample = rng.normal(loc=170.0, scale=8.0, size=600)

    fig, ax = plt.subplots(figsize=(4.2, 3.0))
    ax.hist(
        sample,
        bins=24,
        density=True,
        color="#4C72B0",
        edgecolor="white",
        linewidth=0.4,
        label="observed",
    )

    grid = np.linspace(sample.min(), sample.max(), 300)
    mean, sd = sample.mean(), sample.std(ddof=1)
    density = np.exp(-0.5 * ((grid - mean) / sd) ** 2) / (sd * np.sqrt(2 * np.pi))
    ax.plot(grid, density, color="#C44E52", linewidth=1.6, label="fitted normal")

    ax.set_xlabel("Measured value")
    ax.set_ylabel("Density")
    ax.legend(frameon=False)
    save(fig, "example-histogram.pdf")


def scatter(rng: np.random.Generator) -> None:
    """Scatter with a least-squares line and its 95% confidence band."""
    x = rng.uniform(0.0, 10.0, size=80)
    y = 2.4 * x + 5.0 + rng.normal(scale=3.5, size=x.size)

    slope, intercept = np.polyfit(x, y, deg=1)
    grid = np.linspace(x.min(), x.max(), 200)
    fit = slope * grid + intercept

    # Standard error of the fitted mean, widening away from x-bar.
    residuals = y - (slope * x + intercept)
    dof = x.size - 2
    sigma = np.sqrt(np.sum(residuals**2) / dof)
    sxx = np.sum((x - x.mean()) ** 2)
    stderr = sigma * np.sqrt(1.0 / x.size + (grid - x.mean()) ** 2 / sxx)
    band = 1.96 * stderr

    fig, ax = plt.subplots(figsize=(3.4, 2.8))
    ax.scatter(x, y, s=14, color="#4C72B0", alpha=0.75, edgecolor="none")
    ax.plot(grid, fit, color="#C44E52", linewidth=1.5)
    ax.fill_between(grid, fit - band, fit + band, color="#C44E52", alpha=0.18,
                    linewidth=0)

    ax.set_xlabel("Predictor")
    ax.set_ylabel("Response")
    save(fig, "example-scatter.pdf")


def boxplot(rng: np.random.Generator) -> None:
    """Box plot comparing the distribution of four groups."""
    groups = ["Control", "Low", "Medium", "High"]
    data = [
        rng.normal(loc=loc, scale=scale, size=size)
        for loc, scale, size in ((20, 4, 90), (23, 5, 90), (27, 4.5, 90), (32, 6, 90))
    ]

    fig, ax = plt.subplots(figsize=(3.4, 2.8))
    parts = ax.boxplot(data, tick_labels=groups, patch_artist=True, widths=0.6)
    for box in parts["boxes"]:
        box.set(facecolor="#4C72B0", alpha=0.55, linewidth=0.8)
    for whisker in parts["whiskers"] + parts["caps"]:
        whisker.set(linewidth=0.8)
    for median in parts["medians"]:
        median.set(color="#C44E52", linewidth=1.4)
    for flier in parts["fliers"]:
        flier.set(marker="o", markersize=2.5, markerfacecolor="#555555",
                  markeredgecolor="none")

    ax.set_xlabel("Treatment group")
    ax.set_ylabel("Outcome")
    save(fig, "example-boxplot.pdf")


def errorbar(rng: np.random.Generator) -> None:
    """Two series measured over time, with standard-error bars."""
    time = np.arange(0, 11, dtype=float)
    fig, ax = plt.subplots(figsize=(3.4, 2.8))

    for label, base, rate, color, marker in (
        ("Method A", 12.0, 3.1, "#4C72B0", "o"),
        ("Method B", 12.0, 2.2, "#55A868", "s"),
    ):
        mean = base + rate * time + rng.normal(scale=1.2, size=time.size)
        stderr = 0.8 + 0.12 * time
        ax.errorbar(
            time,
            mean,
            yerr=stderr,
            label=label,
            color=color,
            marker=marker,
            markersize=3.5,
            linewidth=1.2,
            elinewidth=0.8,
            capsize=2,
        )

    ax.set_xlabel("Time (h)")
    ax.set_ylabel("Yield")
    ax.legend(frameon=False)
    save(fig, "example-errorbar.pdf")


def main() -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    # One generator per plot, each seeded off the same root, so editing one
    # plot cannot shift the random draws of the others.
    root = np.random.SeedSequence(SEED)
    for draw, plot in zip(root.spawn(4), (histogram, scatter, boxplot, errorbar)):
        plot(np.random.default_rng(draw))


if __name__ == "__main__":
    main()
