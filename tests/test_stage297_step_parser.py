from src.tools.ege13_report import extract_solution_steps
from src.tools.solution_steps import split_solution_step_texts


def test_case_b_compact_confirmed_transcript_is_split_into_math_steps():
    text = r"""13. a) 1 - \cos 2x + \sqrt{2} \sin x = \sqrt{2} - 2 \sin(x + \pi) \quad 1 - (1 - 2\sin^2 x) + \sqrt{2}\sin x = \sqrt{2} + 2\sin x \quad 2\sin^2 x - 2\sin x + \sqrt{2}\sin x - \sqrt{2} = 0 \quad 2\sin x(\sin x - 1) + \sqrt{2}(\sin x - 1)=0 \quad (2\sin x + \sqrt{2})(\sin x - 1)=0 \quad \sin x=-\frac{\sqrt{2}}{2} \text{ или } \sin x=1 \quad x=-\frac{\pi}{4}+2\pi k,\ x=\frac{\pi}{2}+2\pi k,\ x=-\frac{3\pi}{4}+2\pi k,\ k\in\mathbb{Z}. \quad б) -\frac{\pi}{4}-2\pi=-\frac{9\pi}{4};\ -\frac{3\pi}{4}-2\pi=-\frac{11\pi}{4};\ -\frac{3\pi}{2}. \quad Ответ: a) \frac{\pi}{2}+2\pi k, -\frac{\pi}{4}+2\pi k, -\frac{3\pi}{4}+2\pi k, k\in\mathbb{Z}; b) -\frac{3\pi}{4}, -\frac{11\pi}{4}, -\frac{9\pi}{4}"""
    steps = split_solution_step_texts(text)
    assert len(steps) >= 11
    assert any("2\\sin x(\\sin x - 1)" in step for step in steps)
    assert any("-\\frac{9\\pi}{4}" in step and "-2\\pi" in step for step in steps)
    assert any(step.startswith("Ответ:") for step in steps)
    assert steps[-1].startswith("b)")
    assert r"-\frac{3\pi}{4}" in steps[-1]


def test_case_a_multiline_ocr_keeps_each_visible_transformation_separate():
    text = r"""a) 1-\cos 2x+\sqrt{2}\sin x=\sqrt{2}-2\sin(x+\pi)\n1-\cos^{2}x+\sin^{2}x+\sqrt{2}\sin x=\sqrt{2}-2(\sin x\cdot\cos\pi+\sin\pi\cdot\cos x)\n1+1+2\sin^{2}x+\sqrt{2}\sin x=\sqrt{2}+2\sin x\n2\sin^{2}x+\sqrt{2}\sin x-\sqrt{2}-2\sin x=0\n2\sin x(\sin x-1)+\sqrt{2}(\sin x-1)=0\n(2\sin x+\sqrt{2})(\sin x-1)=0\n\begin{cases}2\sin x+\sqrt{2}=0\\\sin x-1=0\end{cases}\quad\begin{cases}\sin x=-\frac{\sqrt{2}}{2}\\\sin x=1\end{cases}\quad\begin{cases}x=(-1)^{k}\cdot(\frac{\pi}{4})+\pi k;\;k\in\mathbb{Z}\\x=\frac{\pi}{2}+2\pi n;\;n\in\mathbb{Z}\end{cases}\nb)\;найдём\;корни\;с\;положительной\;тупоанометрической\;окружности\nx_{1}=-3\pi+\frac{\pi}{4}=-\frac{11\pi}{4}\nx_{2}=-2\pi-\frac{\pi}{4}=-\frac{9\pi}{4}\nx_{3}=-\frac{3\pi}{2}"""
    steps = extract_solution_steps(text)
    assert len(steps) >= 13
    assert steps[0]["text"].startswith("a)")
    assert any(row["text"].startswith("x_{1}=") for row in steps)
    assert any(row["text"].startswith("x_{2}=") for row in steps)
    assert any(row["text"].startswith("x_{3}=") for row in steps)
    assert not any(row["text"] == r"\text{" for row in steps)


def test_latex_spacing_semicolon_does_not_split_words():
    text = r"b)\;найдём\;корни\;с\;окружности\nx_1=-11\pi/4\nx_2=-9\pi/4"
    steps = split_solution_step_texts(text)
    assert steps[0].startswith(r"b)\;найдём\;корни")
    assert len(steps) == 3
