"""
Roundtrip preservation tests — verify that comments, @variables,
@[expr] expressions, and unmodified formatting survive load-edit-save.
"""
import os
import sys
import unittest

# Ensure offscreen mode for Qt
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

sys.path.insert(0, os.path.dirname(__file__))

from src.core.pdx_parser import PDXParser, parse_file_with_spans, SourceSpan
from src.core.gui_model import (
    GUIDocument, WidgetNode, parse_gui_file, parse_gui_text,
)
from src.codegen.gui_writer import (
    write_document, write_document_preserving, save_document,
)


SAMPLE_GUI = """\
@portrait_x = 0 #立绘左上角X坐标，有需要可调整
@portrait_y = 100 #立绘左上角Y坐标，有需要可调整
@hide_x = 100000

# 这是一段全局注释

guiTypes = {

\t# 主容器窗口
\tcontainerWindowType = {
\t\tname = "test_window"
\t\tposition = { x = @[ -440 / 2 + 26 ] y = 0 }
\t\tsize = { width = @hide_x height = 600 }
\t\torientation = center
\t\tmoveable = yes

\t\t# 内部图标注释
\t\ticonType = {
\t\t\tname = "portrait_icon"
\t\t\tspriteType = "GFX_leader_bg_1"
\t\t\tposition = { x = @portrait_x y = @portrait_y }
\t\t\tscale = 0.8
\t\t}

\t\tbuttonType = {
\t\t\tname = "close_button"
\t\t\tspriteType = "GFX_close"
\t\t\tposition = { x = -42 y = 8 }
\t\t\torientation = UPPER_RIGHT
\t\t}
\t}

\t# 第二个容器
\tcontainerWindowType = {
\t\tname = "second_window"
\t\tposition = { x = 100 y = 200 }
\t\tsize = { width = 300 height = 400 }
\t}
}
"""


class TestParserSpans(unittest.TestCase):
    """Test that the parser correctly tracks source spans."""

    def test_tokenizer_offsets(self):
        from src.core.pdx_parser import tokenize
        text = 'name = "test"'
        tokens = tokenize(text)
        self.assertEqual(tokens[0].value, 'name')
        self.assertEqual(tokens[0].offset, 0)
        self.assertEqual(tokens[1].value, '=')
        self.assertEqual(tokens[1].offset, 5)
        self.assertEqual(tokens[2].value, '"test"')
        self.assertEqual(tokens[2].offset, 7)

    def test_parse_with_spans(self):
        parser = PDXParser(SAMPLE_GUI)
        result = parser.parse_with_spans()
        self.assertTrue(result.raw_source)
        self.assertIsNotNone(result.guitypes_span)
        self.assertIsNotNone(result.guitypes_inner_span)
        # Should find 2 top-level widgets in guiTypes
        self.assertEqual(len(result.widget_spans), 2)
        # First widget should be containerWindowType
        self.assertEqual(result.widget_spans[0].widget_type, 'containerWindowType')
        # Second widget should also be containerWindowType
        self.assertEqual(result.widget_spans[1].widget_type, 'containerWindowType')

    def test_span_text_extraction(self):
        parser = PDXParser(SAMPLE_GUI)
        result = parser.parse_with_spans()
        for span_info in result.widget_spans:
            span_text = SAMPLE_GUI[span_info.full_span.start:span_info.full_span.end]
            # The extracted text should start with the widget type
            self.assertTrue(span_text.strip().startswith('containerWindowType'),
                            f'Span text does not start with widget type: {span_text[:50]}...')
            # And end with a closing brace
            self.assertTrue(span_text.rstrip().endswith('}'),
                            f'Span text does not end with }}: {span_text[-20:]}')


class TestRoundtripNoEdit(unittest.TestCase):
    """Test that a load-save cycle with no edits preserves the file exactly."""

    def test_no_edit_roundtrip(self):
        doc = parse_gui_text(SAMPLE_GUI, 'test.gui')
        result = write_document_preserving(doc)
        self.assertEqual(result, SAMPLE_GUI,
                         'File should be exactly preserved when no edits are made')

    def test_comments_preserved(self):
        doc = parse_gui_text(SAMPLE_GUI, 'test.gui')
        result = write_document_preserving(doc)
        self.assertIn('#立绘左上角X坐标，有需要可调整', result)
        self.assertIn('#立绘左上角Y坐标，有需要可调整', result)
        self.assertIn('# 这是一段全局注释', result)
        self.assertIn('# 主容器窗口', result)
        self.assertIn('# 内部图标注释', result)
        self.assertIn('# 第二个容器', result)

    def test_variables_preserved(self):
        doc = parse_gui_text(SAMPLE_GUI, 'test.gui')
        result = write_document_preserving(doc)
        self.assertIn('@portrait_x = 0', result)
        self.assertIn('@portrait_y = 100', result)
        self.assertIn('@hide_x = 100000', result)

    def test_expressions_preserved(self):
        doc = parse_gui_text(SAMPLE_GUI, 'test.gui')
        result = write_document_preserving(doc)
        self.assertIn('@[ -440 / 2 + 26 ]', result)

    def test_variable_references_preserved(self):
        doc = parse_gui_text(SAMPLE_GUI, 'test.gui')
        result = write_document_preserving(doc)
        self.assertIn('@portrait_x', result)
        self.assertIn('@portrait_y', result)
        self.assertIn('@hide_x', result)


class TestRoundtripWithEdits(unittest.TestCase):
    """Test that edits only affect modified widgets, preserving the rest."""

    def test_modify_second_widget_preserves_first(self):
        doc = parse_gui_text(SAMPLE_GUI, 'test.gui')
        # Modify the second widget
        second = doc.roots[1]
        self.assertEqual(second.name, 'second_window')
        second.position = (150, 250)

        result = write_document_preserving(doc)
        # First widget and all global content should be preserved exactly
        self.assertIn('@portrait_x = 0 #立绘左上角X坐标，有需要可调整', result)
        self.assertIn('@portrait_y = 100 #立绘左上角Y坐标，有需要可调整', result)
        self.assertIn('# 这是一段全局注释', result)
        self.assertIn('# 主容器窗口', result)
        self.assertIn('@[ -440 / 2 + 26 ]', result)
        self.assertIn('# 内部图标注释', result)
        # Second widget's position should be updated
        self.assertIn('150', result)
        self.assertIn('250', result)

    def test_modify_child_preserves_sibling(self):
        doc = parse_gui_text(SAMPLE_GUI, 'test.gui')
        # The first root has children; modify the close_button
        first_root = doc.roots[0]
        close_btn = None
        for child in first_root.children:
            if child.name == 'close_button':
                close_btn = child
                break
        self.assertIsNotNone(close_btn)
        close_btn.position = (10, 20)

        result = write_document_preserving(doc)
        # Global content preserved
        self.assertIn('@portrait_x = 0 #立绘左上角X坐标，有需要可调整', result)
        self.assertIn('# 这是一段全局注释', result)
        # Second widget preserved
        self.assertIn('# 第二个容器', result)

    def test_new_file_uses_traditional_write(self):
        """New files without raw_source should use write_document fallback."""
        doc = GUIDocument(file_path='new.gui')
        node = WidgetNode(widget_type='containerWindowType')
        node.properties = {
            'name': 'new_widget',
            'position': {'x': 0, 'y': 0},
            'size': {'width': 200, 'height': 150},
        }
        doc.roots.append(node)
        result = write_document_preserving(doc)
        self.assertIn('guiTypes', result)
        self.assertIn('new_widget', result)


class TestSourceModifiedTracking(unittest.TestCase):
    """Test that _source_modified is correctly set."""

    def test_position_setter_marks_modified(self):
        node = WidgetNode(widget_type='iconType')
        node.properties = {'name': 'test', 'position': {'x': 0, 'y': 0}}
        node._source_modified = False
        node.position = (10, 20)
        self.assertTrue(node._source_modified)

    def test_size_setter_marks_modified(self):
        node = WidgetNode(widget_type='iconType')
        node.properties = {'name': 'test'}
        node._source_modified = False
        node.size = (100, 200)
        self.assertTrue(node._source_modified)

    def test_clone_marks_modified(self):
        node = WidgetNode(widget_type='iconType')
        node.properties = {'name': 'test'}
        node._source_modified = False
        cloned = node.clone()
        self.assertTrue(cloned._source_modified)

    def test_subtree_modified_check(self):
        parent = WidgetNode(widget_type='containerWindowType')
        parent.properties = {'name': 'parent'}
        child = WidgetNode(widget_type='iconType')
        child.properties = {'name': 'child'}
        parent.add_child(child)

        parent._source_modified = False
        child._source_modified = False
        self.assertFalse(parent.is_subtree_modified())

        child._source_modified = True
        self.assertTrue(parent.is_subtree_modified())


class TestEdgeCases(unittest.TestCase):
    """Edge case tests."""

    def test_file_without_guitypes_wrapper(self):
        """Some files may have widgets outside guiTypes."""
        text = """\
containerWindowType = {
    name = "bare_widget"
    position = { x = 0 y = 0 }
}
"""
        doc = parse_gui_text(text, 'bare.gui')
        # Should still parse
        self.assertEqual(len(doc.roots), 1)

    def test_multiple_guitypes_blocks(self):
        """Handle files with content before guiTypes."""
        text = """\
@my_var = 42

guiTypes = {
    iconType = {
        name = "icon1"
        position = { x = 0 y = 0 }
    }
}
"""
        doc = parse_gui_text(text, 'test.gui')
        result = write_document_preserving(doc)
        self.assertIn('@my_var = 42', result)
        self.assertIn('icon1', result)

    def test_empty_document(self):
        doc = GUIDocument()
        result = write_document_preserving(doc)
        # Should use traditional write
        self.assertIn('guiTypes', result)

    def test_percentage_values_preserved(self):
        text = """\
guiTypes = {
    containerWindowType = {
        name = "pct_test"
        size = { width = 100% height = 50% }
    }
}
"""
        doc = parse_gui_text(text, 'test.gui')
        result = write_document_preserving(doc)
        self.assertIn('100%', result)
        self.assertIn('50%', result)


if __name__ == '__main__':
    unittest.main()
