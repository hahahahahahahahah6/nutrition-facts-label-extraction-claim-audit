"""Contract tests use temporary repositories and fixed reference literals."""
import ast
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from nutrition_facts_label_extraction_claim_audit.audit import audit, match_phrases, normalize, source_evidence
from nutrition_facts_label_extraction_claim_audit.phrases import NUTRITIONFACTSLABELEXTRACTION, NONUTRITIONFACTSLABELEXTRACTION, GENERIC_NAMES
from nutrition_facts_label_extraction_claim_audit.__main__ import main

EXPECTED_POS = ('nutrition facts label extraction', 'extract nutrition facts labels', 'extracts nutrition facts labels', 'extracting nutrition facts labels', 'extract nutrition facts label', 'extracts nutrition facts label', 'extracting nutrition facts label', 'nutrition facts label parsing', 'nutrition facts label parser', 'parse nutrition facts labels', 'parses nutrition facts labels', 'parse nutrition facts label', 'parses nutrition facts label', 'nutrition facts label scanning', 'nutrition facts label scanner', 'scan nutrition facts labels', 'scans nutrition facts labels', 'scan nutrition facts label', 'scans nutrition facts label', 'nutrition facts extraction', 'extract nutrition facts', 'extracts nutrition facts', 'extracting nutrition facts', 'nutrition facts parsing', 'nutrition facts parser', 'parse nutrition facts', 'parses nutrition facts', 'nutrition facts scanning', 'nutrition facts scanner', 'scan nutrition facts', 'scans nutrition facts', 'nutrition label extraction', 'extract nutrition labels', 'extracts nutrition labels', 'extracting nutrition labels', 'extract nutrition label', 'extracts nutrition label', 'extracting nutrition label', 'nutrition label parsing', 'nutrition label parser', 'parse nutrition labels', 'parses nutrition labels', 'parse nutrition label', 'parses nutrition label', 'nutrition label scanning', 'nutrition label scanner', 'scan nutrition labels', 'scans nutrition labels', 'scan nutrition label', 'scans nutrition label')
EXPECTED_NEG = ('no nutrition facts label extraction', 'does not extract nutrition facts labels', 'does not extract nutrition facts label', 'does not support nutrition facts label extraction', 'without nutrition facts label extraction', 'no nutrition facts label parser', 'does not parse nutrition facts labels', 'does not parse nutrition facts label', 'no nutrition facts extraction', 'does not extract nutrition facts', 'does not support nutrition facts extraction', 'without nutrition facts extraction', 'no nutrition facts parser', 'does not parse nutrition facts', 'no nutrition label extraction', 'does not extract nutrition labels', 'does not extract nutrition label', 'does not support nutrition label extraction', 'without nutrition label extraction', 'no nutrition label parser', 'does not parse nutrition labels', 'does not parse nutrition label', 'no nutrition facts label scanner', 'nutrition facts label extraction not supported')
EXPECTED_NAMES = ('extract_nutrition_facts_label', 'parse_nutrition_facts_label', 'extract_nutrition_facts_labels', 'parse_nutrition_facts_labels', 'extract_nutrition_facts', 'parse_nutrition_facts', 'extract_nutrition_label', 'parse_nutrition_label', 'extract_nutrition_labels', 'parse_nutrition_labels', 'nutrition_facts_label_extraction', 'nutrition_facts_label_extractor', 'nutrition_facts_label_parser', 'nutrition_facts_extraction', 'nutrition_facts_extractor', 'nutrition_facts_parser', 'nutrition_label_extraction', 'nutrition_label_extractor', 'nutrition_label_parser', 'extract_nutrition_facts_label_data', 'parse_nutrition_facts_label_data', 'nutrition_facts_label_scan', 'nutrition_facts_label_scanner', 'scan_nutrition_facts_label')

class AuditTests(unittest.TestCase):
    def repo(self, files):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        for name, content in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        return root

    def cli(self, root, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(['audit', str(root), '--json', *args])
        return code, json.loads(out.getvalue())

    def test_phrase_oracle(self):
        source = Path(__file__).resolve().parents[1] / 'nutrition_facts_label_extraction_claim_audit' / 'phrases.py'
        parsed = {node.targets[0].id: ast.literal_eval(node.value)
                  for node in ast.parse(source.read_text()).body if isinstance(node, ast.Assign)}
        self.assertEqual(parsed['NUTRITIONFACTSLABELEXTRACTION'], EXPECTED_POS)
        self.assertEqual(parsed['NONUTRITIONFACTSLABELEXTRACTION'], EXPECTED_NEG)
        self.assertEqual(parsed['GENERIC_NAMES'], EXPECTED_NAMES)
        self.assertEqual(NUTRITIONFACTSLABELEXTRACTION, EXPECTED_POS)
        self.assertEqual(NONUTRITIONFACTSLABELEXTRACTION, EXPECTED_NEG)
        self.assertEqual(GENERIC_NAMES, EXPECTED_NAMES)
        self.assertEqual((len(EXPECTED_POS), len(EXPECTED_NEG), len(set(EXPECTED_NAMES))), (50, 24, 24))

    def test_good(self):
        self.assertEqual(self.cli(self.repo({'README.md': 'nutrition facts label extraction', 'app.py': 'x.extract_nutrition_facts_label()'}))[0], 0)

    def test_bad(self):
        code, result = self.cli(self.repo({'README.md': 'nutrition facts label extraction'}))
        self.assertEqual(code, 2)
        self.assertEqual(result['findings'][0]['rule'], 'documented-nutrition-facts-label-extraction-claim-false')
        self.assertEqual(result['findings'][0]['severity'], 'HIGH')
        self.assertTrue(result['findings'][0]['message'])
        self.assertEqual(result['verdict'], 'FAIL')
        self.assertIn('test_evidence', result)
        self.assertIn('production_evidence', result)

    def test_denial(self):
        code, result = self.cli(self.repo({'README.md': 'no nutrition facts label extraction', 'app.py': 'x.extract_nutrition_facts_label()'}))
        self.assertEqual(code, 2)
        self.assertEqual(result['findings'][0]['rule'], 'documented-no-nutrition-facts-label-extraction-claim-false')
        self.assertEqual(result['findings'][0]['severity'], 'HIGH')

    def test_no_source_denial(self):
        self.assertEqual(audit(self.repo({'README.md': 'no nutrition facts label extraction'}))['verdict'], 'PASS')

    def test_no_claim(self):
        self.assertEqual(audit(self.repo({'README.md': 'neutral', 'app.py': 'x.extract_nutrition_facts_label()'}))['verdict'], 'PASS')

    def test_test_only(self):
        for filename in ('tests/helper.py', 'test_feature.py', 'feature_test.py'):
            with self.subTest(filename=filename):
                root = self.repo({'README.md': 'nutrition facts label extraction', filename: 'x.extract_nutrition_facts_label()'})
                code, result = self.cli(root)
                self.assertEqual(code, 0)
                self.assertEqual(result['verdict'], 'PASS')
                self.assertEqual(result['findings'][0]['severity'], 'MEDIUM')
                code, result = self.cli(root, '--fail-on', 'medium')
                self.assertEqual(code, 2)
                self.assertEqual(result['verdict'], 'FAIL')

    def test_ignore_component_prefix(self):
        root = self.repo({'README.md': 'nutrition facts label extraction', 'src/a.py': 'x.extract_nutrition_facts_label()'})
        self.assertEqual(self.cli(root, '--ignore', 'sr')[0], 0)
        self.assertEqual(self.cli(root, '--ignore', 'src')[0], 2)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['audit', str(root), '--ignore', '../outside']), 1)
            self.assertEqual(main(['audit', str(root), '--ignore', '/abs']), 1)

    def test_fences(self):
        for fence in ('```', '~~~', '   ````'):
            root = self.repo({'README.md': fence + '\nnutrition facts label extraction\n' + fence})
            self.assertEqual(audit(root)['verdict'], 'PASS')
        root = self.repo({'README.md': '`nutrition facts label extraction`'})
        self.assertEqual(self.cli(root)[0], 2)

    def test_boundaries_longest_denial(self):
        yes, no = match_phrases('extract nutrition facts label')
        self.assertEqual([p[0] for p in yes], ['extract nutrition facts label'])
        self.assertFalse(match_phrases('preextract nutrition facts labeluffix')[0])
        yes, no = match_phrases('does not extract nutrition facts label')
        self.assertEqual(yes, [])
        self.assertEqual([p[0] for p in no], ['does not extract nutrition facts label'])
        self.assertEqual(match_phrases("doesn't extract nutrition facts label")[0], [])
        self.assertEqual(normalize('NUTRITION-FACTS-LABEL  extraction'), 'nutrition facts label extraction')

    def test_invalid_encoding_declaration(self):
        root = self.repo({'README.md': 'nutrition facts label extraction', 'app.py': '# coding: nonexistent-r208\nx.extract_nutrition_facts_label()'})
        self.assertEqual(self.cli(root)[0], 2)

    def test_attribute_assignment_preserves_import(self):
        self.assertTrue(source_evidence('import mindee\nmindee.setting = True\nmindee.Client()\nx.parse(NutritionFactsLabelV1)'))

    def test_single_module(self):
        root = self.repo({'README.md': 'nutrition facts label extraction', 'one.py': 'import mindee\nc=mindee.Client()', 'two.py': 'x.parse(product.NutritionFactsLabelV1)'})
        self.assertEqual(self.cli(root)[0], 2)

    def test_paths_and_ignore(self):
        for folder in ('fixtures', 'docs', 'examples'):
            root = self.repo({'README.md': 'nutrition facts label extraction', folder+'/a.py': 'x.extract_nutrition_facts_label()'})
            self.assertEqual(self.cli(root)[0], 2)
        root = self.repo({'nested/docs/a.md': 'nutrition facts label extraction', 'other.md': 'no nutrition facts label extraction', 'vendor/a.py': 'x.extract_nutrition_facts_label()'})
        self.assertEqual(self.cli(root)[0], 0)
        self.assertEqual(self.cli(root, '--ignore', 'vendor', '--ignore', 'unused')[0], 2)
        self.assertEqual(self.cli(root, '--ignore', 'nested')[0], 0)

    def test_symlinks(self):
        root = self.repo({'README.md': 'nutrition facts label extraction'})
        outside = self.repo({'a.py': 'x.extract_nutrition_facts_label()', 'a.md': 'nutrition facts label extraction'})
        (root/'link.py').symlink_to(outside/'a.py')
        (root/'linked').symlink_to(outside, target_is_directory=True)
        self.assertEqual(self.cli(root)[0], 2)
        (root/'README.md').unlink()
        (root/'README.md').symlink_to(outside/'a.md')
        self.assertEqual(audit(root)['verdict'], 'PASS')

    def test_usage_io(self):
        for argv in ([], ['audit', '--fail-on', 'HIGH'], ['audit', '--unknown']):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                main(argv)
            self.assertEqual(caught.exception.code, 1)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['audit', '/nonexistent/r208']), 1)
        root = self.repo({})
        root.chmod(0)
        try:
            with self.assertRaises(OSError): audit(root)
        finally:
            root.chmod(0o700)

    def test_entry_points(self):
        root = self.repo({})
        command = [sys.executable, '-m', 'nutrition_facts_label_extraction_claim_audit']
        self.assertEqual(subprocess.check_output(command+['--version'], text=True).strip(), '0.1.0')
        result = subprocess.run(command+['audit', str(root), '--json'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)['verdict'], 'PASS')


    def test_positive_000(self):
        self.assertTrue(source_evidence('x.extract_nutrition_facts_label()'))

    def test_positive_001(self):
        self.assertTrue(source_evidence('from provider import extract_nutrition_facts_label as run\nrun()'))

    def test_positive_002(self):
        self.assertTrue(source_evidence('from provider import extract_nutrition_facts_label\nextract_nutrition_facts_label()'))

    def test_positive_003(self):
        self.assertTrue(source_evidence('x.parse_nutrition_facts_label()'))

    def test_positive_004(self):
        self.assertTrue(source_evidence('from provider import parse_nutrition_facts_label as run\nrun()'))

    def test_positive_005(self):
        self.assertTrue(source_evidence('from provider import parse_nutrition_facts_label\nparse_nutrition_facts_label()'))

    def test_positive_006(self):
        self.assertTrue(source_evidence('x.extract_nutrition_facts_labels()'))

    def test_positive_007(self):
        self.assertTrue(source_evidence('from provider import extract_nutrition_facts_labels as run\nrun()'))

    def test_positive_008(self):
        self.assertTrue(source_evidence('from provider import extract_nutrition_facts_labels\nextract_nutrition_facts_labels()'))

    def test_positive_009(self):
        self.assertTrue(source_evidence('x.parse_nutrition_facts_labels()'))

    def test_positive_010(self):
        self.assertTrue(source_evidence('from provider import parse_nutrition_facts_labels as run\nrun()'))

    def test_positive_011(self):
        self.assertTrue(source_evidence('from provider import parse_nutrition_facts_labels\nparse_nutrition_facts_labels()'))

    def test_positive_012(self):
        self.assertTrue(source_evidence('x.extract_nutrition_facts()'))

    def test_positive_013(self):
        self.assertTrue(source_evidence('from provider import extract_nutrition_facts as run\nrun()'))

    def test_positive_014(self):
        self.assertTrue(source_evidence('from provider import extract_nutrition_facts\nextract_nutrition_facts()'))

    def test_positive_015(self):
        self.assertTrue(source_evidence('x.parse_nutrition_facts()'))

    def test_positive_016(self):
        self.assertTrue(source_evidence('from provider import parse_nutrition_facts as run\nrun()'))

    def test_positive_017(self):
        self.assertTrue(source_evidence('from provider import parse_nutrition_facts\nparse_nutrition_facts()'))

    def test_positive_018(self):
        self.assertTrue(source_evidence('x.extract_nutrition_label()'))

    def test_positive_019(self):
        self.assertTrue(source_evidence('from provider import extract_nutrition_label as run\nrun()'))

    def test_positive_020(self):
        self.assertTrue(source_evidence('from provider import extract_nutrition_label\nextract_nutrition_label()'))

    def test_positive_021(self):
        self.assertTrue(source_evidence('x.parse_nutrition_label()'))

    def test_positive_022(self):
        self.assertTrue(source_evidence('from provider import parse_nutrition_label as run\nrun()'))

    def test_positive_023(self):
        self.assertTrue(source_evidence('from provider import parse_nutrition_label\nparse_nutrition_label()'))

    def test_positive_024(self):
        self.assertTrue(source_evidence('x.extract_nutrition_labels()'))

    def test_positive_025(self):
        self.assertTrue(source_evidence('from provider import extract_nutrition_labels as run\nrun()'))

    def test_positive_026(self):
        self.assertTrue(source_evidence('from provider import extract_nutrition_labels\nextract_nutrition_labels()'))

    def test_positive_027(self):
        self.assertTrue(source_evidence('x.parse_nutrition_labels()'))

    def test_positive_028(self):
        self.assertTrue(source_evidence('from provider import parse_nutrition_labels as run\nrun()'))

    def test_positive_029(self):
        self.assertTrue(source_evidence('from provider import parse_nutrition_labels\nparse_nutrition_labels()'))

    def test_positive_030(self):
        self.assertTrue(source_evidence('x.nutrition_facts_label_extraction()'))

    def test_positive_031(self):
        self.assertTrue(source_evidence('from provider import nutrition_facts_label_extraction as run\nrun()'))

    def test_positive_032(self):
        self.assertTrue(source_evidence('from provider import nutrition_facts_label_extraction\nnutrition_facts_label_extraction()'))

    def test_positive_033(self):
        self.assertTrue(source_evidence('x.nutrition_facts_label_extractor()'))

    def test_positive_034(self):
        self.assertTrue(source_evidence('from provider import nutrition_facts_label_extractor as run\nrun()'))

    def test_positive_035(self):
        self.assertTrue(source_evidence('from provider import nutrition_facts_label_extractor\nnutrition_facts_label_extractor()'))

    def test_positive_036(self):
        self.assertTrue(source_evidence('x.nutrition_facts_label_parser()'))

    def test_positive_037(self):
        self.assertTrue(source_evidence('from provider import nutrition_facts_label_parser as run\nrun()'))

    def test_positive_038(self):
        self.assertTrue(source_evidence('from provider import nutrition_facts_label_parser\nnutrition_facts_label_parser()'))

    def test_positive_039(self):
        self.assertTrue(source_evidence('x.nutrition_facts_extraction()'))

    def test_positive_040(self):
        self.assertTrue(source_evidence('from provider import nutrition_facts_extraction as run\nrun()'))

    def test_positive_041(self):
        self.assertTrue(source_evidence('from provider import nutrition_facts_extraction\nnutrition_facts_extraction()'))

    def test_positive_042(self):
        self.assertTrue(source_evidence('x.nutrition_facts_extractor()'))

    def test_positive_043(self):
        self.assertTrue(source_evidence('from provider import nutrition_facts_extractor as run\nrun()'))

    def test_positive_044(self):
        self.assertTrue(source_evidence('from provider import nutrition_facts_extractor\nnutrition_facts_extractor()'))

    def test_positive_045(self):
        self.assertTrue(source_evidence('x.nutrition_facts_parser()'))

    def test_positive_046(self):
        self.assertTrue(source_evidence('from provider import nutrition_facts_parser as run\nrun()'))

    def test_positive_047(self):
        self.assertTrue(source_evidence('from provider import nutrition_facts_parser\nnutrition_facts_parser()'))

    def test_positive_048(self):
        self.assertTrue(source_evidence('x.nutrition_label_extraction()'))

    def test_positive_049(self):
        self.assertTrue(source_evidence('from provider import nutrition_label_extraction as run\nrun()'))

    def test_positive_050(self):
        self.assertTrue(source_evidence('from provider import nutrition_label_extraction\nnutrition_label_extraction()'))

    def test_positive_051(self):
        self.assertTrue(source_evidence('x.nutrition_label_extractor()'))

    def test_positive_052(self):
        self.assertTrue(source_evidence('from provider import nutrition_label_extractor as run\nrun()'))

    def test_positive_053(self):
        self.assertTrue(source_evidence('from provider import nutrition_label_extractor\nnutrition_label_extractor()'))

    def test_positive_054(self):
        self.assertTrue(source_evidence('x.nutrition_label_parser()'))

    def test_positive_055(self):
        self.assertTrue(source_evidence('from provider import nutrition_label_parser as run\nrun()'))

    def test_positive_056(self):
        self.assertTrue(source_evidence('from provider import nutrition_label_parser\nnutrition_label_parser()'))

    def test_positive_057(self):
        self.assertTrue(source_evidence('x.extract_nutrition_facts_label_data()'))

    def test_positive_058(self):
        self.assertTrue(source_evidence('from provider import extract_nutrition_facts_label_data as run\nrun()'))

    def test_positive_059(self):
        self.assertTrue(source_evidence('from provider import extract_nutrition_facts_label_data\nextract_nutrition_facts_label_data()'))

    def test_positive_060(self):
        self.assertTrue(source_evidence('x.parse_nutrition_facts_label_data()'))

    def test_positive_061(self):
        self.assertTrue(source_evidence('from provider import parse_nutrition_facts_label_data as run\nrun()'))

    def test_positive_062(self):
        self.assertTrue(source_evidence('from provider import parse_nutrition_facts_label_data\nparse_nutrition_facts_label_data()'))

    def test_positive_063(self):
        self.assertTrue(source_evidence('x.nutrition_facts_label_scan()'))

    def test_positive_064(self):
        self.assertTrue(source_evidence('from provider import nutrition_facts_label_scan as run\nrun()'))

    def test_positive_065(self):
        self.assertTrue(source_evidence('from provider import nutrition_facts_label_scan\nnutrition_facts_label_scan()'))

    def test_positive_066(self):
        self.assertTrue(source_evidence('x.nutrition_facts_label_scanner()'))

    def test_positive_067(self):
        self.assertTrue(source_evidence('from provider import nutrition_facts_label_scanner as run\nrun()'))

    def test_positive_068(self):
        self.assertTrue(source_evidence('from provider import nutrition_facts_label_scanner\nnutrition_facts_label_scanner()'))

    def test_positive_069(self):
        self.assertTrue(source_evidence('x.scan_nutrition_facts_label()'))

    def test_positive_070(self):
        self.assertTrue(source_evidence('from provider import scan_nutrition_facts_label as run\nrun()'))

    def test_positive_071(self):
        self.assertTrue(source_evidence('from provider import scan_nutrition_facts_label\nscan_nutrition_facts_label()'))

    def test_positive_072(self):
        self.assertTrue(source_evidence('import mindee\nmindee.Client()\nx.parse(NutritionFactsLabelV1)'))

    def test_positive_073(self):
        self.assertTrue(source_evidence('import mindee\nmindee.Client()\nx.parse(product_class=NutritionFactsLabelV1)'))

    def test_positive_074(self):
        self.assertTrue(source_evidence('from mindee import Client as C\nfrom mindee.product import NutritionFactsLabelV1\nC()\nx.parse(NutritionFactsLabelV1)'))

    def test_positive_075(self):
        self.assertTrue(source_evidence('from mindee import Client as C\nfrom mindee.product import NutritionFactsLabelV1\nC()\nx.parse(product_class=NutritionFactsLabelV1)'))

    def test_positive_076(self):
        self.assertTrue(source_evidence('import mindee as m\nm.Client()\nx.parse(NutritionFactsLabelV1)'))

    def test_positive_077(self):
        self.assertTrue(source_evidence('import mindee as m\nm.Client()\nx.parse(product_class=NutritionFactsLabelV1)'))

    def test_positive_078(self):
        self.assertTrue(source_evidence('import mindee\nmindee.Client()\nx.parse(product.NutritionFactsLabelV1)'))

    def test_positive_079(self):
        self.assertTrue(source_evidence('import mindee\nmindee.Client()\nx.parse(product_class=product.NutritionFactsLabelV1)'))

    def test_positive_080(self):
        self.assertTrue(source_evidence('from mindee import Client as C\nfrom mindee.product import NutritionFactsLabelV1\nC()\nx.parse(product.NutritionFactsLabelV1)'))

    def test_positive_081(self):
        self.assertTrue(source_evidence('from mindee import Client as C\nfrom mindee.product import NutritionFactsLabelV1\nC()\nx.parse(product_class=product.NutritionFactsLabelV1)'))

    def test_positive_082(self):
        self.assertTrue(source_evidence('import mindee as m\nm.Client()\nx.parse(product.NutritionFactsLabelV1)'))

    def test_positive_083(self):
        self.assertTrue(source_evidence('import mindee as m\nm.Client()\nx.parse(product_class=product.NutritionFactsLabelV1)'))

    def test_positive_084(self):
        self.assertTrue(source_evidence('import mindee\nmindee.Client()\nx.parse(mindee.product.NutritionFactsLabelV1)'))

    def test_positive_085(self):
        self.assertTrue(source_evidence('import mindee\nmindee.Client()\nx.parse(product_class=mindee.product.NutritionFactsLabelV1)'))

    def test_positive_086(self):
        self.assertTrue(source_evidence('from mindee import Client as C\nfrom mindee.product import NutritionFactsLabelV1\nC()\nx.parse(mindee.product.NutritionFactsLabelV1)'))

    def test_positive_087(self):
        self.assertTrue(source_evidence('from mindee import Client as C\nfrom mindee.product import NutritionFactsLabelV1\nC()\nx.parse(product_class=mindee.product.NutritionFactsLabelV1)'))

    def test_positive_088(self):
        self.assertTrue(source_evidence('import mindee as m\nm.Client()\nx.parse(mindee.product.NutritionFactsLabelV1)'))

    def test_positive_089(self):
        self.assertTrue(source_evidence('import mindee as m\nm.Client()\nx.parse(product_class=mindee.product.NutritionFactsLabelV1)'))

    def test_positive_090(self):
        self.assertTrue(source_evidence('import mindee\nmindee.Client()\nx.parse(mindee.product.nutrition_facts_label.NutritionFactsLabelV1)'))

    def test_positive_091(self):
        self.assertTrue(source_evidence('import mindee\nmindee.Client()\nx.parse(product_class=mindee.product.nutrition_facts_label.NutritionFactsLabelV1)'))

    def test_positive_092(self):
        self.assertTrue(source_evidence('from mindee import Client as C\nfrom mindee.product import NutritionFactsLabelV1\nC()\nx.parse(mindee.product.nutrition_facts_label.NutritionFactsLabelV1)'))

    def test_positive_093(self):
        self.assertTrue(source_evidence('from mindee import Client as C\nfrom mindee.product import NutritionFactsLabelV1\nC()\nx.parse(product_class=mindee.product.nutrition_facts_label.NutritionFactsLabelV1)'))

    def test_positive_094(self):
        self.assertTrue(source_evidence('import mindee as m\nm.Client()\nx.parse(mindee.product.nutrition_facts_label.NutritionFactsLabelV1)'))

    def test_positive_095(self):
        self.assertTrue(source_evidence('import mindee as m\nm.Client()\nx.parse(product_class=mindee.product.nutrition_facts_label.NutritionFactsLabelV1)'))

    def test_negative_000(self):
        self.assertEqual(source_evidence('import mindee'), [])

    def test_negative_001(self):
        self.assertEqual(source_evidence('import veryfi'), [])

    def test_negative_002(self):
        self.assertEqual(source_evidence('import azure.ai.formrecognizer'), [])

    def test_negative_003(self):
        self.assertEqual(source_evidence('import azure.ai.documentintelligence'), [])

    def test_negative_004(self):
        self.assertEqual(source_evidence('import google.cloud.documentai'), [])

    def test_negative_005(self):
        self.assertEqual(source_evidence('import nutritionix'), [])

    def test_negative_006(self):
        self.assertEqual(source_evidence('import boto3'), [])

    def test_negative_007(self):
        self.assertEqual(source_evidence('import edamam'), [])

    def test_negative_008(self):
        self.assertEqual(source_evidence('import openfoodfacts'), [])

    def test_negative_009(self):
        self.assertEqual(source_evidence('import mindee\nmindee.Client()\nx.parse(InvoiceV4)'), [])

    def test_negative_010(self):
        self.assertEqual(source_evidence('import mindee\nmindee.Client()\nx.parse(ReceiptV5)'), [])

    def test_negative_011(self):
        self.assertEqual(source_evidence('import mindee\nmindee.Client()\nx.parse(PassportV1)'), [])

    def test_negative_012(self):
        self.assertEqual(source_evidence('import mindee\nmindee.Client()\nx.parse(FinancialDocumentV1)'), [])

    def test_negative_013(self):
        self.assertEqual(source_evidence('import mindee\nmindee.Client()\nx.parse(BankCheckV1)'), [])

    def test_negative_014(self):
        self.assertEqual(source_evidence('import mindee\nmindee.Client()\nx.parse(BankAccountDetailsV1)'), [])

    def test_negative_015(self):
        self.assertEqual(source_evidence('import mindee\nmindee.Client()\nx.parse(BankAccountDetailsV2)'), [])

    def test_negative_016(self):
        self.assertEqual(source_evidence('import mindee\nmindee.Client()\nx.parse(PayslipV2)'), [])

    def test_negative_017(self):
        self.assertEqual(source_evidence('import mindee\nmindee.Client()\nx.parse(PayslipV3)'), [])

    def test_negative_018(self):
        self.assertEqual(source_evidence('import mindee\nmindee.Client()\nx.parse(HealthcareCardV1)'), [])

    def test_negative_019(self):
        self.assertEqual(source_evidence('import mindee\nmindee.Client()\nx.parse(BusinessCardV1)'), [])

    def test_negative_020(self):
        self.assertEqual(source_evidence('import mindee\nmindee.Client()\nx.parse(CustomV1)'), [])

    def test_negative_021(self):
        self.assertEqual(source_evidence('import mindee\nmindee.Client()\nx.parse(GeneratedV1)'), [])

    def test_negative_022(self):
        self.assertEqual(source_evidence('import mindee\nmindee.Client()\nx.parse(BillOfLadingV1)'), [])

    def test_negative_023(self):
        self.assertEqual(source_evidence('import mindee\nmindee.Client()\nx.parse(ResumeV1)'), [])

    def test_negative_024(self):
        self.assertEqual(source_evidence('import mindee\nmindee.Client()\nx.parse(DeliveryNoteV1)'), [])

    def test_negative_025(self):
        self.assertEqual(source_evidence('import mindee\nmindee.Client()\nx.parse(DriverLicenseV1)'), [])

    def test_negative_026(self):
        self.assertEqual(source_evidence('import mindee\nmindee.Client()\nx.parse(IdCardV1)'), [])

    def test_negative_027(self):
        self.assertEqual(source_evidence('import mindee\nmindee.Client()\nx.parse(InternationalIdV2)'), [])

    def test_negative_028(self):
        self.assertEqual(source_evidence('import mindee\nmindee.Client()\nx.parse(CarteGriseV1)'), [])

    def test_negative_029(self):
        self.assertEqual(source_evidence('import mindee\nmindee.Client()\nx.parse(EnergyBillV1)'), [])

    def test_negative_030(self):
        self.assertEqual(source_evidence('import mindee\nmindee.Client()\nx.parse(BarcodeReaderV1)'), [])

    def test_negative_031(self):
        self.assertEqual(source_evidence('import mindee\nmindee.Client()\nx.parse(CropperV1)'), [])

    def test_negative_032(self):
        self.assertEqual(source_evidence('import mindee\nmindee.Client()\nx.parse(TypeNutritionFactsLabelV1)'), [])

    def test_negative_033(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-invoice')"), [])

    def test_negative_034(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-receipt')"), [])

    def test_negative_035(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-layout')"), [])

    def test_negative_036(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-read')"), [])

    def test_negative_037(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-idDocument')"), [])

    def test_negative_038(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-check.us')"), [])

    def test_negative_039(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-tax.us')"), [])

    def test_negative_040(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-bankStatement.us')"), [])

    def test_negative_041(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-payStub.us')"), [])

    def test_negative_042(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-healthInsuranceCard.us')"), [])

    def test_negative_043(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-businessCard')"), [])

    def test_negative_044(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-creditCard')"), [])

    def test_negative_045(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-contract')"), [])

    def test_negative_046(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-mortgage.us.1003')"), [])

    def test_negative_047(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-vaccinationCard')"), [])

    def test_negative_048(self):
        self.assertEqual(source_evidence('x.process_any_document()'), [])

    def test_negative_049(self):
        self.assertEqual(source_evidence('x.process_any_document_url()'), [])

    def test_negative_050(self):
        self.assertEqual(source_evidence('x.process_document()'), [])

    def test_negative_051(self):
        self.assertEqual(source_evidence('x.process_document_url()'), [])

    def test_negative_052(self):
        self.assertEqual(source_evidence('x.process_w2_document()'), [])

    def test_negative_053(self):
        self.assertEqual(source_evidence('x.process_w9_document()'), [])

    def test_negative_054(self):
        self.assertEqual(source_evidence('x.process_w8_document()'), [])

    def test_negative_055(self):
        self.assertEqual(source_evidence('x.process_check()'), [])

    def test_negative_056(self):
        self.assertEqual(source_evidence('x.process_check_url()'), [])

    def test_negative_057(self):
        self.assertEqual(source_evidence('x.process_check_with_remittance()'), [])

    def test_negative_058(self):
        self.assertEqual(source_evidence('x.process_check_with_remittance_url()'), [])

    def test_negative_059(self):
        self.assertEqual(source_evidence('x.process_bank_statement_document()'), [])

    def test_negative_060(self):
        self.assertEqual(source_evidence('x.process_bank_statement_document_url()'), [])

    def test_negative_061(self):
        self.assertEqual(source_evidence('x.process_bussines_card_document()'), [])

    def test_negative_062(self):
        self.assertEqual(source_evidence('x.process_bussines_card_document_url()'), [])

    def test_negative_063(self):
        self.assertEqual(source_evidence('x.classify_document()'), [])

    def test_negative_064(self):
        self.assertEqual(source_evidence('x.get_business_cards()'), [])

    def test_negative_065(self):
        self.assertEqual(source_evidence('x.get_business_card()'), [])

    def test_negative_066(self):
        self.assertEqual(source_evidence('x.delete_business_card()'), [])

    def test_negative_067(self):
        self.assertEqual(source_evidence('x.process_nutrition_facts_label_document()'), [])

    def test_negative_068(self):
        self.assertEqual(source_evidence('x.process_nutrition_facts_label_document_url()'), [])

    def test_negative_069(self):
        self.assertEqual(source_evidence('x.batch_process_documents()'), [])

    def test_negative_070(self):
        self.assertEqual(source_evidence('x.analyze_document()'), [])

    def test_negative_071(self):
        self.assertEqual(source_evidence('x.analyze_expense()'), [])

    def test_negative_072(self):
        self.assertEqual(source_evidence('x.analyze_id()'), [])

    def test_negative_073(self):
        self.assertEqual(source_evidence('x.start_document_analysis()'), [])

    def test_negative_074(self):
        self.assertEqual(source_evidence('x.get_expense_analysis()'), [])

    def test_negative_075(self):
        self.assertEqual(source_evidence('x.extract_text()'), [])

    def test_negative_076(self):
        self.assertEqual(source_evidence('x.image_to_string()'), [])

    def test_negative_077(self):
        self.assertEqual(source_evidence('x.read_csv()'), [])

    def test_negative_078(self):
        self.assertEqual(source_evidence('x.read_excel()'), [])

    def test_negative_079(self):
        self.assertEqual(source_evidence('x.read_pdf()'), [])

    def test_negative_080(self):
        self.assertEqual(source_evidence('x.convert_into()'), [])

    def test_negative_081(self):
        self.assertEqual(source_evidence('x.extract_table()'), [])

    def test_negative_082(self):
        self.assertEqual(source_evidence('x.extract_tables()'), [])

    def test_negative_083(self):
        self.assertEqual(source_evidence('x.find_table()'), [])

    def test_negative_084(self):
        self.assertEqual(source_evidence('x.find_tables()'), [])

    def test_negative_085(self):
        self.assertEqual(source_evidence('import mindee\nmindee.Client()'), [])

    def test_negative_086(self):
        self.assertEqual(source_evidence('import veryfi\nveryfi.Client()'), [])

    def test_negative_087(self):
        self.assertEqual(source_evidence('from azure.ai.documentintelligence import DocumentIntelligenceClient\nDocumentIntelligenceClient()'), [])

    def test_negative_088(self):
        self.assertEqual(source_evidence('x.parse(NutritionFactsLabelV1)'), [])

    def test_negative_089(self):
        self.assertEqual(source_evidence('import mindee\nx.parse(NutritionFactsLabelV1)'), [])

    def test_negative_090(self):
        self.assertEqual(source_evidence('mindee.Client()\nx.parse(NutritionFactsLabelV1)'), [])

    def test_negative_091(self):
        self.assertEqual(source_evidence('requests.post("https://api.veryfi.com/api/v8/partner/documents")'), [])

    def test_negative_092(self):
        self.assertEqual(source_evidence('x.post("universal-ai", json={"model":"ocr/invoice_parser/affinda"})'), [])

    def test_negative_093(self):
        self.assertEqual(source_evidence('x.post("universal-ai", json={"model":"ocr/resume_parser/affinda"})'), [])

    def test_negative_094(self):
        self.assertEqual(source_evidence('LlamaParse().parse("file")'), [])

    def test_negative_095(self):
        self.assertEqual(source_evidence('nanonets.ocr(model_id="opaque")'), [])

    def test_negative_096(self):
        self.assertEqual(source_evidence('docsumo.upload("file")'), [])

    def test_negative_097(self):
        self.assertEqual(source_evidence('mindee.ClientV2().enqueue_and_parse(model_id="opaque")'), [])

    def test_negative_098(self):
        self.assertEqual(source_evidence('re.search("calories", text)'), [])

    def test_negative_099(self):
        self.assertEqual(source_evidence('re.findall("protein", text)'), [])

    def test_negative_100(self):
        self.assertEqual(source_evidence('str.parse("nutrition facts")'), [])

    def test_negative_101(self):
        self.assertEqual(source_evidence('subprocess.run(["mindee", "parse"])'), [])

    def test_negative_102(self):
        self.assertEqual(source_evidence('subprocess.run(["veryfi", "process"])'), [])

    def test_negative_103(self):
        self.assertEqual(source_evidence('x.extract_nutrition_facts_label'), [])

    def test_negative_104(self):
        self.assertEqual(source_evidence('extract_nutrition_facts_label()'), [])

    def test_negative_105(self):
        self.assertEqual(source_evidence('this is invalid !'), [])

    def test_negative_106(self):
        self.assertEqual(source_evidence('text = "x.extract_nutrition_facts_label()"'), [])

    def test_negative_107(self):
        self.assertEqual(source_evidence('# x.extract_nutrition_facts_label()'), [])

    def test_negative_108(self):
        self.assertEqual(source_evidence('nutritionix.search("food")'), [])

    def test_negative_109(self):
        self.assertEqual(source_evidence('edamam.search("food")'), [])

    def test_negative_110(self):
        self.assertEqual(source_evidence('openfoodfacts.products.get("barcode")'), [])

    def test_negative_111(self):
        self.assertEqual(source_evidence('usda.search("food")'), [])

    def test_negative_112(self):
        self.assertEqual(source_evidence('barcode.lookup("upc")'), [])

    def test_negative_113(self):
        self.assertEqual(source_evidence('abbyy.upload("opaque")'), [])

    def test_negative_114(self):
        self.assertEqual(source_evidence('rossum.upload("opaque")'), [])

    def test_negative_115(self):
        self.assertEqual(source_evidence('klippa.upload("opaque")'), [])

    def test_negative_116(self):
        self.assertEqual(source_evidence('parseur.upload("opaque")'), [])

    def test_negative_117(self):
        self.assertEqual(source_evidence('extend.upload("opaque")'), [])

    def test_negative_118(self):
        self.assertEqual(source_evidence('def extract_nutrition_facts_label(): pass\nx.extract_nutrition_facts_label()'), [])

    def test_negative_119(self):
        self.assertEqual(source_evidence('class X:\n def extract_nutrition_facts_label(self): pass\nx.extract_nutrition_facts_label()'), [])

    def test_negative_120(self):
        self.assertEqual(source_evidence('from p import extract_nutrition_facts_label as run\nrun = other\nrun()'), [])

    def test_negative_121(self):
        self.assertEqual(source_evidence('from p import extract_nutrition_facts_label as run\nrun: object = other\nrun()'), [])

    def test_negative_122(self):
        self.assertEqual(source_evidence('from p import extract_nutrition_facts_label as run\nwith context() as run:\n pass\nrun()'), [])

    def test_negative_123(self):
        self.assertEqual(source_evidence('from p import extract_nutrition_facts_label as run\nasync def f():\n async with context() as run:\n  pass\nrun()'), [])

    def test_negative_124(self):
        self.assertEqual(source_evidence('def parse_nutrition_facts_label(): pass\nx.parse_nutrition_facts_label()'), [])

    def test_negative_125(self):
        self.assertEqual(source_evidence('class X:\n def parse_nutrition_facts_label(self): pass\nx.parse_nutrition_facts_label()'), [])

    def test_negative_126(self):
        self.assertEqual(source_evidence('from p import parse_nutrition_facts_label as run\nrun = other\nrun()'), [])

    def test_negative_127(self):
        self.assertEqual(source_evidence('from p import parse_nutrition_facts_label as run\nrun: object = other\nrun()'), [])

    def test_negative_128(self):
        self.assertEqual(source_evidence('from p import parse_nutrition_facts_label as run\nwith context() as run:\n pass\nrun()'), [])

    def test_negative_129(self):
        self.assertEqual(source_evidence('from p import parse_nutrition_facts_label as run\nasync def f():\n async with context() as run:\n  pass\nrun()'), [])

    def test_negative_130(self):
        self.assertEqual(source_evidence('import mindee\nclass Client: pass\nmindee.Client()\nx.parse(NutritionFactsLabelV1)'), [])

    def test_negative_131(self):
        self.assertEqual(source_evidence('import mindee\nclass NutritionFactsLabelV1: pass\nmindee.Client()\nx.parse(NutritionFactsLabelV1)'), [])

    def test_negative_132(self):
        self.assertEqual(source_evidence('import mindee\ndef parse(): pass\nmindee.Client()\nx.parse(NutritionFactsLabelV1)'), [])

    def test_all_phrases(self):
        for phrase in EXPECTED_POS:
            self.assertEqual([p[0] for p in match_phrases(phrase)[0]], [phrase])
        for phrase in EXPECTED_NEG:
            yes, no = match_phrases(phrase)
            self.assertEqual(yes, [])
            self.assertEqual([p[0] for p in no], [phrase])

    def test_readme(self):
        root = self.repo({'README.md': (Path(__file__).resolve().parents[1]/'README.md').read_text()})
        self.assertEqual(self.cli(root)[0], 0)

    def test_dead_code(self):
        self.assertTrue(source_evidence('raise RuntimeError()\nif False: x.extract_nutrition_facts_label()'))

    def test_console_callable(self):
        import importlib.metadata
        entry = importlib.metadata.EntryPoint(name='nutrition-facts-label-extraction-claim-audit', value='nutrition_facts_label_extraction_claim_audit.__main__:main', group='console_scripts')
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as caught:
            entry.load()(['--version'])
        self.assertEqual(caught.exception.code, 0)

    def test_mindee_bound_aliases(self):
        for binding in ('C = other', 'C: object = other', 'with context() as C:\n pass',
                        'async def f():\n async with context() as C:\n  pass'):
            self.assertEqual(source_evidence('from mindee import Client as C\n' + binding +
                                            '\nC()\nx.parse(NutritionFactsLabelV1)'), [])

    def test_alphabetical_order(self):
        from nutrition_facts_label_extraction_claim_audit.audit import _matches
        self.assertEqual([p[0] for p in _matches('bb aa', ('bb', 'aa'))], ['aa', 'bb'])
