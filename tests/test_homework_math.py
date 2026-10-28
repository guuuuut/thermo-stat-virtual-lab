"""Protect the assignment's Markdown-to-MathJax boundary."""
import unittest
from scripts.build_homework_materials import assignment_html, inline_markdown


class HomeworkMathTest(unittest.TestCase):
    def test_display_equation_is_a_separate_escaped_block(self):
        result = assignment_html('## 题五\n\n说明\n\n$$\nD(L)=D_\\infty-A/L\n$$\n\n后文')
        self.assertIn('<div class="math-display">\\[\nD(L)=D_\\infty-A/L\n\\]</div>', result)
        self.assertNotIn('<p>$$', result)
        self.assertIn('<p>后文</p>', result)
        self.assertIn('&lt;', assignment_html('$$\nx<1\n$$'))

    def test_inline_math_and_code_are_not_markdown_emphasis(self):
        result = inline_markdown('**提示** $D_{**x**}$ `vacf`')
        self.assertIn('<strong>提示</strong>', result)
        self.assertIn('$D_{**x**}$', result)
        self.assertIn('<code>vacf</code>', result)

    def test_invalid_display_blocks_fail_the_build(self):
        for source in ['$$\nx=1', '$$\n$$']:
            with self.subTest(source=source), self.assertRaises(ValueError):
                assignment_html(source)


if __name__ == '__main__':
    unittest.main()
