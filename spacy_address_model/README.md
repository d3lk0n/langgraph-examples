# Training custom NER model for address recognition with Spacy

The majority of this code was written by @AnnemarieWittig within: https://github.com/WSE-research/Qanary-NER-automl-component

## How to train

```bash
python3 generate_spacy_data.py
python3 -m spacy train ./config/config.cfg --paths.train ./corpus/spacy-docbins/train.spacy --paths.dev ./corpus/spacy-docbins/test.spacy --output ./
```

## How to use the trained model

Check the `test_model.py` file or:

```python
import spacy


nlp_ner = spacy.load("model-best")

doc = nlp_ner("I live in Leipzig, Gustav-Freytag-Straße 42a.")

print("Entities", [(ent.text, ent.label_) for ent in doc.ents])
```

## Official Spacy documentation

For the further improvements, check the docs here: https://spacy.io/usage/training
