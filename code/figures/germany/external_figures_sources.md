# Energy-Charts and BNetzA figure collection

The electricity-mix and installed-power figures use Energy-Charts. The tariff figures use annual anchors from the Bundesnetzagentur's official EEG archive. An annual anchor is not an annual average: tariffs changed within many years.

Primary sources:

- [Energy-Charts API](https://api.energy-charts.info/) — machine-readable installed power and generation endpoints.
- [Energy-Charts 2025 electricity-generation chart](https://www.energy-charts.info/charts/power/chart.htm?c=DE&interval=year&l=en&legendItems=my6&source=public&year=2025).
- [Bundesnetzagentur EEG archive](https://www.bundesnetzagentur.de/DE/Fachthemen/ElektrizitaetundGas/ErneuerbareEnergien/EEG_Foerderung/Archiv_VergSaetze/start.html) — official historical tariff workbooks/PDFs.
- [Bundesnetzagentur current EEG rates](https://www.bundesnetzagentur.de/DE/Fachthemen/ElektrizitaetundGas/ErneuerbareEnergien/EEG_Foerderung/start.html) — current rates and the distinction between partial and full feed-in.
- [EEG 2023, official legal text](https://www.gesetze-im-internet.de/eeg_2014/BJNR106610014.html).

Regenerate the figures with `poetry run python main.py external-figures`.
