---
name: Excel formulas
description: Write and explain Excel or Google Sheets formulas for everyday office calculations.
---
When asked for a spreadsheet formula:

1. State the assumption about where the data is (for example "amount in B2, rate in C2"). Ask only if the layout is truly unclear.
2. Give the formula in a code block, ready to paste. Prefer modern functions that work in both Excel and Google Sheets (IF, SUMIFS, XLOOKUP or VLOOKUP, TEXT, EDATE, PMT, ROUND).
3. Explain it in 2 to 3 plain sentences: what each part does.
4. Show a tiny worked example with real-looking numbers so the user can check it.
5. Mention one common mistake (absolute references with $, text that looks like numbers, date formats).

For loan or EMI maths use PMT with rate/12 and years*12 and say the result is an estimate. For Indian number formatting mention TEXT(value,"#,##,##0") when relevant. Keep answers short; do not write macros unless asked.
