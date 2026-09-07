#!/usr/bin/env python3
"""CPU-only acceptance of the installed XgrammarGrammar methods, via AST.

Run inside the candidate image without --gpus. A fake matcher isolates the
termination bookkeeping; the live canary separately tests real XGrammar.
"""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

SOURCE = Path('/usr/local/lib/python3.12/dist-packages/vllm/v1/structured_output/backend_xgrammar.py')


class Matcher:
    def __init__(self):
        self.tokens = []

    def accept_token(self, token):
        if self.is_terminated() or token == 99:
            return False
        self.tokens.append(token)
        return True

    def is_terminated(self):
        return 2 in self.tokens

    def rollback(self, count):
        if not 0 <= count <= len(self.tokens):
            raise ValueError('invalid rollback')
        if count:
            del self.tokens[-count:]

    def reset(self):
        self.tokens.clear()


def grammar():
    tree = ast.parse(SOURCE.read_text())
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == 'XgrammarGrammar')
    cls.bases = []
    cls.decorator_list = []
    cls.body = [node for node in cls.body if isinstance(node, ast.FunctionDef)
                and node.name in {'accept_tokens', 'validate_tokens', 'rollback', 'reset', 'is_terminated'}]
    module = ast.Module(body=[cls], type_ignores=[])
    namespace = {'logger': SimpleNamespace(error=lambda *args: None)}
    exec(compile(ast.fix_missing_locations(module), str(SOURCE), 'exec'), namespace)
    result = namespace['XgrammarGrammar']()
    result.matcher = Matcher()
    result.num_processed_tokens = 0
    result._is_terminated = False
    return result


class TerminationTests(unittest.TestCase):
    def test_batch_stops_at_first_eos(self):
        item = grammar()
        self.assertTrue(item.accept_tokens('test', [1, 2, 3]))
        self.assertEqual(item.matcher.tokens, [1, 2])
        self.assertEqual(item.num_processed_tokens, 2)
        self.assertTrue(item.is_terminated())

    def test_second_advance_is_noop(self):
        item = grammar()
        self.assertTrue(item.accept_tokens('test', [2]))
        self.assertTrue(item.accept_tokens('test', [3]))
        self.assertEqual(item.num_processed_tokens, 1)

    def test_validation_restores_matcher_after_eos(self):
        item = grammar()
        self.assertEqual(item.validate_tokens([1, 2, 3]), [1, 2])
        self.assertEqual(item.matcher.tokens, [])
        self.assertFalse(item.is_terminated())
        self.assertEqual(item.num_processed_tokens, 0)

    def test_validate_after_termination_is_empty(self):
        item = grammar()
        item.accept_tokens('test', [2])
        self.assertEqual(item.validate_tokens([3]), [])
        self.assertEqual(item.matcher.tokens, [2])

    def test_reset_clears_cached_termination(self):
        item = grammar()
        item.accept_tokens('test', [2])
        item.reset()
        self.assertFalse(item.is_terminated())
        self.assertTrue(item.accept_tokens('test', [1]))
        self.assertEqual(item.num_processed_tokens, 1)

    def test_real_rejection_is_not_swallowed(self):
        item = grammar()
        self.assertFalse(item.accept_tokens('test', [99]))
        self.assertEqual(item.num_processed_tokens, 0)

    def test_rollback_reopens_terminated_state(self):
        item = grammar()
        item.accept_tokens('test', [1, 2])
        item.rollback(1)
        self.assertFalse(item.is_terminated())
        self.assertEqual(item.num_processed_tokens, 1)
        self.assertTrue(item.accept_tokens('test', [2]))


if __name__ == '__main__':
    unittest.main()
