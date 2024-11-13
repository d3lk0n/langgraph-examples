import spacy


# Download the model: python -m spacy download en_core_web_sm

# Load the small English model
nlp = spacy.load("en_core_web_sm")

def simple_ner(text):
    doc = nlp(text)
    entities = [(ent.text, ent.label_) for ent in doc.ents]
    return entities


if __name__ == "__main__":
    # Example usage
    text = "I want to order a pizza. The address is: Gustav-Freytag-Straße 42a Leipzig"
    results = simple_ner(text)
    for entity, label in results:
        print(f"Entity: {entity} - Label: {label}")