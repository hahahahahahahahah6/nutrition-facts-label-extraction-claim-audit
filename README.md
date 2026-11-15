# Documentation claim auditor

An offline static audit tool for comparing documentation promises with Python source fingerprints. It reads root README.md and Markdown files with a docs path component, parses source with AST, and never executes the inspected code. It uses no network, sends no telemetry, and writes no audit files.

## Usage

```sh
python3 -m pip install .
nutrition-facts-label-extraction-claim-audit --version
nutrition-facts-label-extraction-claim-audit audit /path/to/repo --json
python3 -m nutrition_facts_label_extraction_claim_audit audit . --verbose
nutrition-facts-label-extraction-claim-audit audit . --fail-on medium --ignore vendor --ignore build
python3 -m unittest discover
python3 -m build
```

Version: 0.1.0. The optional repository argument defaults to the current directory. Ignore values are relative path component prefixes, each supplied separately. The failure threshold is lowercase high (default) or medium. Exit codes are 0 for PASS, 2 for findings meeting the threshold, and 1 for usage or I/O errors. JSON includes verdict, findings (rule, severity, message, locations), production_evidence, and test_evidence. Verbose text includes evidence paths and lines.

```text
Claims without production evidence:
  documented-nutrition-facts-label-extraction-claim-false HIGH
  MEDIUM instead when evidence exists only in tests
Denials contradicted by production evidence:
  documented-no-nutrition-facts-label-extraction-claim-false HIGH
```

Each family produces at most one finding. A claim without any source files fails; a denial without source passes. Findings below the threshold remain in the report.

## Matching and evidence

Fenced code blocks using backticks or tildes with up to three leading spaces are omitted. Inline code counts. Paragraphs split on blank lines; matching lowercases text, expands contractions, converts hyphens to spaces and collapses whitespace. Exact phrases use word boundaries, longest first with alphabetical ties. Denial spans are removed before positive matching. The fixed vocabularies live in phrases.py.

Symlinked files and directories are excluded. Source under fixtures, docs, or examples cannot supply evidence. Files under tests, or named test_*.py or *_test.py, supply only test evidence. Invalid syntax supplies none. Imports, assignments, annotated assignments, and with/async-with bindings are tracked per module. Local function, method, or class definitions shadow route names. Evidence cannot be combined across modules.

```text
The accepted SDK route requires a mindee import, Client construction,
and .parse(... NutritionFactsLabelV1 ...) in one module. The product
argument may be a Name or an Attribute with that exact final name,
positional or keyword. Imported Client aliases are resolved.
The product can be accessed through mindee.product or
mindee.product.nutrition_facts_label. There is no TypeNutritionFactsLabelV1 route.
Generic routes are exactly the 24 names in GENERIC_NAMES: attribute
calls on any base, or imported names (including aliases). Bare unimported
name calls do not count.
```

The Mindee product was present in SDK 4.22.0 and removed in 5.x (absent in 5.4.0). Detection concerns the source call, not the installed version, API success, credentials, or field correctness. Azure Document Intelligence, Mindee, and Veryfi are cloud APIs; this audit does not contact them.

The accepted product carries serving_size, serving_per_box, calories, total_fat, saturated_fat, trans_fat, cholesterol, sodium, total_carbohydrate, dietary_fiber, total_sugars, added_sugars, protein, and nutrients. It has no brand, ingredient, allergen, net weight, or manufacturer field. Other field sets require other routes; this checker checks the product call only.

## Limitations

Static pattern matching is not semantic judgement. Dead code counts; unsupported alias chains are missed; denial handling depends on the fixed list. A listed generic call can parse manually typed strings rather than documents and still count. A bare string operation with no listed call does not count. Diet logs, stored or displayed records, meal planners, rendered label templates, keyword highlighters, photographs, or raw OCR can cause misleading documentation matches.

```text
Deliberately broad claim wording includes:
"nutrition facts extraction", "extract nutrition facts",
"nutrition facts parsing", "nutrition facts parser",
"nutrition label extraction", "extract nutrition label",
"nutrition label parsing", "nutrition label parser",
"nutrition facts label scanning", "scan nutrition facts label",
"nutrition facts label parsing", "nutrition facts label parser".
These can describe storage, display, templates, photography, OCR, or
highlighting instead of structured document fields. The phrases trigger
the audit; only the code determines evidence.
```

Other Mindee products are not accepted, including the following:

```text
InvoiceV4 ReceiptV5 PassportV1 FinancialDocumentV1 BankCheckV1
BankAccountDetailsV1 BankAccountDetailsV2 PayslipV2 PayslipV3
HealthcareCardV1 BusinessCardV1 CustomV1 GeneratedV1 BillOfLadingV1
ResumeV1 DeliveryNoteV1 DriverLicenseV1 IdCardV1 InternationalIdV2
CarteGriseV1 EnergyBillV1 BarcodeReaderV1 CropperV1
```

Barcode reading and UPC lookup retrieve database information rather than structured panel fields. Nutritionix, Edamam, Open Food Facts, and USDA FoodData Central database queries are excluded for the same reason. Handwritten regular expressions on OCR text with manual field assembly are missed unless they use a listed call. Plain text, OCR, CSV, spreadsheet and table operations alone do not count. External commands invoked through subprocess, including the Mindee and Veryfi CLIs, do not count.

There is no Azure route for any model identifier: the v4.0 GA model list had no corresponding model when checked on 2026-11-14. There is no Veryfi route of any kind: SDK 5.1.0 has no corresponding method, and its generic documents HTTP endpoint is shared by multiple document types. Invented method names do not count. Google Document AI has no corresponding processor, so neither individual nor batch processing counts. Eden AI has no corresponding parser model, regardless of model identifier. LlamaParse is generative and has no fixed fingerprint. Nanonets, Docsumo, ABBYY Vantage, Rossum, Klippa, Parseur, Extend, and Mindee v2 use opaque or configurable model, skill, queue, template, or workflow identifiers, or generic uploads configured elsewhere. Textract document, expense and identity analysis operations do not count.

The following topics do not belong to the phrase vocabulary; single nutrient values, ingredients, plain text, label creation, verification and broader packaging are different operations:

```text
extract calories / calorie extraction / extract protein / extract sodium
extract ingredients / ingredient extraction
extract nutrition facts text / extract text from nutrition facts labels
nutrition facts label template / nutrition facts label form
nutrition facts verification / nutrition verification
food label extraction / extract food labels
```

Other document families are outside this check: invoices, receipts, identity documents, checks, statements, tax forms, pay stubs, insurance cards, business cards, credit cards, contracts, mortgages, resumes, bills of lading, delivery notes, vehicle registrations, energy bills, marriage certificates, and RIB documents. Their claims and evidence alone do not establish the checked capability.

MIT licensed. Requires Python 3.9 or newer; runtime uses only the standard library.
