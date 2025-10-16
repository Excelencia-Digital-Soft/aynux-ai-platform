import spacy

try:
    # Load the Spanish model
    nlp_es = spacy.load("es_core_news_sm")
    print("✅ Modelo de español (es_core_news_sm) cargado exitosamente.")

    # Test with a sample sentence
    doc_es = nlp_es("Hola, esto es una prueba del modelo de spaCy en español.")
    print(f'   Tokens: {[token.text for token in doc_es]}\n')

except IOError:
    print("❌ Error: No se pudo cargar el modelo de español 'es_core_news_sm'.")

try:
    # Load the English model
    nlp_en = spacy.load("en_core_web_sm")
    print("✅ Modelo de inglés (en_core_web_sm) cargado exitosamente.")

    # Test with a sample sentence
    doc_en = nlp_en("Hello, this is a test of the English spaCy model.")
    print(f'   Tokens: {[token.text for token in doc_en]}\n')

except IOError:
    print("❌ Error: Could not load the English model 'en_core_web_sm'.")
