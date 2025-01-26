# app.py
from flask import Flask, render_template, request
from uralicNLP.cg3 import Cg3
from uralicNLP import tokenizer
import re
import xml.etree.ElementTree as ET

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

def extract_text_from_elan_xml(xml_file, tier_suffix):
    """
    Extract text from ELAN XML file for tiers containing the specified suffix
    """
    tree = ET.parse(xml_file)
    root = tree.getroot()
    
    # Find all tiers whose TIER_ID contains the specified suffix
    matching_tiers = [
        tier for tier in root.findall('.//TIER') 
        if tier_suffix in tier.get('TIER_ID', '')
    ]
    
    # Extract annotations from matching tiers
    extracted_texts = []
    for tier in matching_tiers:
        annotations = tier.findall('.//ANNOTATION_VALUE')
        extracted_texts.extend([
            ann.text.strip() for ann in annotations 
            if ann.text and ann.text.strip()
        ])
    
    return ' '.join(extracted_texts)

@app.route('/', methods=['GET', 'POST'])
def analyze_text():
    text = ''
    disambiguations = []
    show_unknown_only = False
    selected_language = 'fin'  # Default to Finnish
    xml_param = request.form.get('xml_param', 'transcription')
    
    if request.method == 'POST':
        text = request.form['text']
        show_unknown_only = 'show_unknown' in request.form
        selected_language = request.form.get('language', 'fin')
        xml_param = request.form.get('xml_param', 'transcription')
        
        # Handle XML file upload
        if 'xml_file' in request.files:
            xml_file = request.files['xml_file']
            if xml_file and xml_file.filename.lower().endswith('.eaf'):
                try:
                    # Extract text from ELAN XML
                    extracted_xml_text = extract_text_from_elan_xml(xml_file, xml_param)
                    
                    # Append extracted text to existing text, if any
                    if extracted_xml_text:
                        text = f"{text} {extracted_xml_text}".strip()
                except Exception as e:
                    print(f"XML Parsing Error: {e}")
        
        if text:
            tokens = tokenizer.words(text)
            cg = Cg3(selected_language)
            
            try:
                cg_results = cg.disambiguate(tokens)
                
                disambiguations = []
                for word, analyses in cg_results:
                    word_analyses = []
                    
                    # Clean morphology tags
                    def clean_morphology(morphology):
                        return [
                            m for m in morphology 
                            if m not in ['<fin>', '<W:0.000000>'] 
                            and not re.match(r'<W:\d+\.\d+>', m)
                        ]
                    
                    # Check if there are valid analyses (first item's lemma is not '?')
                    if analyses and analyses[0].morphology[0] != '?':
                        for analysis in analyses:
                            morphology = clean_morphology(analysis.morphology)
                            
                            word_analyses.append({
                                'lemma': analysis.lemma,
                                'morphology': morphology
                            })
                    else:
                        # Handle unknown words
                        word_analyses.append({
                            'lemma': word,
                            'morphology': ['Unknown']
                        })
                    
                    disambiguations.append({
                        'word': word,
                        'analyses': word_analyses
                    })
                
                # Filter for unknown words if requested
                if show_unknown_only:
                    disambiguations = [
                        item for item in disambiguations 
                        if item['analyses'][0]['morphology'][0] == 'Unknown'
                    ]
            
            except Exception as e:
                print(f"Analysis Error: {e}")
    
    return render_template('index.html', 
                           text=text, 
                           disambiguations=disambiguations, 
                           show_unknown_only=show_unknown_only,
                           selected_language=selected_language,
                           xml_param=xml_param)

if __name__ == '__main__':
    app.run(debug=True)