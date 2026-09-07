#!/usr/bin/env python3
"""CPU regression for the installed manager's actual grammar_bitmask method.

AST extraction avoids loading vLLM/CUDA. The matcher and tensor are test doubles;
live MTP tests separately exercise the real model and XGrammar backend.
"""
import __future__
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

SOURCE = Path('/usr/local/lib/python3.12/dist-packages/vllm/v1/structured_output/__init__.py')


class Tensor:
    shape = (32,)

    def __getitem__(self, key):
        return self

    def numpy(self):
        return 'bitmask'


class Grammar:
    def __init__(self):
        self.tokens = []
        self.errors = []
        self.advances = []
        self.validations = []
        self.rollbacks = []

    def is_terminated(self):
        return False

    def accept_tokens(self, request_id, tokens):
        if any(token not in (1, 2) for token in tokens):
            self.errors.append(tokens)
            return False
        self.tokens.extend(tokens)
        self.advances.append(tokens)
        return True

    def validate_tokens(self, tokens):
        self.validations.append(tokens)
        return tokens if all(token in (1, 2) for token in tokens) else []

    def rollback(self, count):
        self.rollbacks.append(count)
        del self.tokens[-count:]


def manager(already_constrained=False):
    tree = ast.parse(SOURCE.read_text())
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == 'StructuredOutputManager')
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef)
                  and node.name == 'grammar_bitmask')
    module = ast.Module(body=[method], type_ignores=[])
    namespace = {'TYPE_CHECKING': False}
    exec(compile(ast.fix_missing_locations(module), str(SOURCE), 'exec',
                 flags=__future__.annotations.compiler_flag), namespace)
    instance = SimpleNamespace(
        vllm_config=SimpleNamespace(num_speculative_tokens=5,
                                   model_config=SimpleNamespace(is_diffusion=False)),
        _grammar_bitmask=Tensor(), fill_bitmask_parallel_threshold=128,
        enable_in_reasoning=False, masks=[],
    )
    instance.should_fill_bitmask = lambda request: already_constrained
    instance._get_reasoner = lambda request: SimpleNamespace(
        is_reasoning_end_streaming=lambda history, delta: delta == [42])
    instance._fill_bitmasks = lambda batch: instance.masks.extend(
        (index, enabled) for grammar, index, enabled in batch)
    instance.run = lambda requests, ids, drafts: namespace['grammar_bitmask'](
        instance, requests, ids, drafts)
    return instance


class ReasoningTests(unittest.TestCase):
    def run_tokens(self, tokens, constrained=False):
        mgr, grammar = manager(constrained), Grammar()
        request = SimpleNamespace(all_token_ids=[10, 11],
                                  structured_output_request=SimpleNamespace(grammar=grammar))
        result = mgr.run({'r': request}, ['r'], {'r': tokens})
        self.assertEqual(result, 'bitmask')
        self.assertEqual(grammar.tokens, [])
        return mgr, grammar

    def test_invalid_post_reasoning_draft_never_advances_or_logs(self):
        mgr, grammar = self.run_tokens([42, 99])
        self.assertEqual(grammar.errors, [])
        self.assertEqual(grammar.validations, [[99]])
        self.assertEqual(grammar.advances, [])
        self.assertEqual(mgr.masks, [(0, False), (1, True), (2, True)])

    def test_valid_post_reasoning_drafts_advance_and_rollback(self):
        _, grammar = self.run_tokens([42, 1, 2])
        self.assertEqual(grammar.validations, [[1], [2]])
        self.assertEqual(grammar.advances, [[1], [2]])
        self.assertEqual(grammar.rollbacks, [2])

    def test_reasoning_tokens_are_not_sent_to_grammar(self):
        mgr, grammar = self.run_tokens([99, 98, 42])
        self.assertEqual(grammar.errors, [])
        self.assertEqual(grammar.validations, [])
        self.assertTrue(mgr.masks[-1][1])

    def test_invalid_constrained_token_still_raises(self):
        with self.assertRaises(AssertionError):
            self.run_tokens([99], constrained=True)

    def test_valid_constrained_tokens_keep_existing_path(self):
        _, grammar = self.run_tokens([1, 2], constrained=True)
        self.assertEqual(grammar.validations, [])
        self.assertEqual(grammar.advances, [[1], [2]])
        self.assertEqual(grammar.rollbacks, [2])

    def test_padding_does_not_advance(self):
        _, grammar = self.run_tokens([42, -1])
        self.assertEqual(grammar.validations, [])
        self.assertEqual(grammar.advances, [])

    def test_no_structured_requests(self):
        self.assertIsNone(manager().run({}, [], {}))


if __name__ == '__main__':
    unittest.main()
