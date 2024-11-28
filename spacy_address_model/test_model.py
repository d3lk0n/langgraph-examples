import spacy


nlp_ner = spacy.load("model-best")

doc = nlp_ner("I live in Leipzig, Germany, Gustav-Freytag-Straße 42a.")

print("Entities", [(ent.text, ent.label_) for ent in doc.ents])
