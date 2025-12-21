import json
import os
import re
from datetime import datetime
from urllib.request import urlopen

from google.auth.transport.requests import Request
from google.oauth2 import service_account
from googleapiclient.discovery import build


def fetch_google_doc(doc_id, creds):
    """Fetch Google Doc content using Docs API"""
    service = build('docs', 'v1', credentials=creds)
    doc = service.documents().get(documentId=doc_id).execute()
    return doc


def extract_text_from_doc(doc_content):
    """Extract all text and structure from Google Doc, tracking bold formatting"""
    sections = {}
    current_section = None
    current_list = []

    for element in doc_content.get('body', {}).get('content', []):
        if 'paragraph' in element:
            paragraph = element.get('paragraph', {})

            # Get all text and track if first run is bold
            text_parts = []
            first_run_bold = False

            for idx, run in enumerate(paragraph.get('elements', [])):
                if 'textRun' in run:
                    text = run['textRun'].get('content', '')
                    text_style = run['textRun'].get('textStyle', {})
                    is_bold = text_style.get('bold', False)

                    # Track if first run (that has content) is bold
                    if idx == 0 and text.strip() and is_bold:
                        first_run_bold = True

                    text_parts.append(text)

            text = ''.join(text_parts).strip()

            if not text:
                if current_list and current_section:
                    sections[current_section] = current_list
                    current_list = []
                continue

            # Detect heading levels
            style = paragraph.get('paragraphStyle', {})
            named_style = style.get('namedStyleType', '')

            if named_style == 'HEADING_1' or named_style == 'HEADING_2':
                if current_list and current_section:
                    sections[current_section] = current_list
                current_section = text
                current_list = []
            else:
                # Check if it's a bullet point
                if paragraph.get('bullet'):
                    current_list.append(text)
                # Check if it's a bold label like "Skills:", "Clients:", "Philosophy:"
                elif first_run_bold and (':' in text or ';' in text):
                    # This is a bold label, add it as a special marker
                    current_list.append(text)
                else:
                    if current_section and current_list:
                        sections[current_section] = current_list
                        current_list = []
                    sections[text] = None

    if current_list and current_section:
        sections[current_section] = current_list

    return sections


def download_pdf(doc_id, creds, output_path):
    """Download Google Doc as PDF"""
    try:
        # ❌ Remove this line - service accounts don't need it
        # creds.refresh(Request())

        drive_service = build('drive', 'v3', credentials=creds)
        request = drive_service.files().export_media(
            fileId=doc_id,
            mimeType='application/pdf'
        )
        pdf_content = request.execute()

        # Save PDF
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(pdf_content)
        print(f"✓ PDF saved to {output_path}")
        return True
    except Exception as e:
        print(f"✗ Error downloading PDF: {e}")
        return False


def generate_resume_html(sections, include_contact=False):
    """Generate resume HTML only for Professional Experience and beyond"""
    html = []

    # Sections to update (skip Professional Summary and Core Technical Skills)
    sections_to_update = [
        'Professional Experience',
        'Projects',
        'Certifications',
        'Education & Training',
        'Awards & Recognition',
        'Early Career Experience',
    ]

    section_mapping = {
        'Professional Experience': ('briefcase', 'Professional Experience'),
        'Projects': ('code-square', 'Featured Projects'),
        'Certifications': ('award', 'Certifications'),
        'Education & Training': ('book', 'Education & Training'),
        'Awards & Recognition': ('star', 'Awards & Recognition'),
        'Early Career Experience': ('clock-history', 'Early Career Experience'),
    }

    for section_name in sections_to_update:
        if section_name not in sections:
            continue

        icon, display_name = section_mapping[section_name]
        content = sections[section_name]

        html.append(f'      <!-- {display_name} -->')
        html.append('      <div class="resume-section">')
        html.append(
            f'        <h3 class="resume-title"><i class="bi bi-{icon}"></i> {display_name}</h3>')

        # Awards - simple list
        if section_name == 'Awards & Recognition':
            html.append('        <ul class="awards-list">')
            if isinstance(content, list):
                for item in content:
                    html.append(f'          <li>{item}</li>')
            html.append('        </ul>')

        # Certifications - badge list
        elif section_name == 'Certifications':
            html.append('        <div class="cert-list">')
            if isinstance(content, list):
                for item in content:
                    html.append(
                        f'          <p><span class="badge-cert">{item}</span></p>')
            html.append('        </div>')

        # Experience & Education - items with title, company/dates, location, bullets
        else:
            if isinstance(content, list):
                i = 0
                while i < len(content):
                    item = content[i]

                    # Skip empty lines
                    if not item or item.strip() == '':
                        i += 1
                        continue

                    html.append('        <div class="resume-item">')
                    html.append(f'          <h4>{item}</h4>')
                    i += 1

                    # Next line: Company | Dates (company name and full time on same line)
                    if i < len(content) and content[i].strip():
                        html.append(f'          <h5>{content[i]}</h5>')
                        i += 1

                    # Next line: Location (in italics)
                    if i < len(content) and content[i].strip():
                        html.append(f'          <p><em>{content[i]}</em></p>')
                        i += 1

                    # Collect bullet points and bold labels until next title or end
                    bullets = []
                    while i < len(content):
                        line = content[i].strip()
                        # Stop if we hit an empty line followed by what looks like a title
                        if not line:
                            i += 1
                            # Check if next non-empty line is a title (starts with capital, followed by role words)
                            j = i
                            while j < len(content) and not content[j].strip():
                                j += 1
                            if j < len(content) and content[j][0].isupper() and not any(content[j].startswith(label) for label in ['Skills:', 'Clients:', 'Philosophy:']):
                                break
                            continue
                        # Check if it's a bold label (Skills:, Clients:, Philosophy:, etc.)
                        is_bold_label = any(line.startswith(label) for label in [
                                            'Skills:', 'Clients:', 'Philosophy:', 'Technologies:'])
                        # If it's a bullet point, bold label, or regular description, add it
                        if line.startswith('•') or line.startswith('-') or is_bold_label or not line[0].isupper():
                            # Clean bullet markers
                            if line.startswith('•') or line.startswith('-'):
                                line = line[1:].strip()
                            bullets.append(line)
                            i += 1
                        else:
                            # Stop at next title
                            break

                    if bullets:
                        html.append('          <ul>')
                        for bullet in bullets:
                            # Check if bullet starts with bold labels like "Skills:", "Clients:", "Philosophy:", etc.
                            if ':' in bullet:
                                potential_label = bullet.split(':')[0].strip()
                                if potential_label in ['Skills', 'Clients', 'Philosophy', 'Technologies']:
                                    label, content_part = bullet.split(':', 1)
                                    html.append(
                                        f'            <li><strong>{label}:</strong>{content_part}</li>')
                                else:
                                    html.append(
                                        f'            <li>{bullet}</li>')
                            else:
                                html.append(f'            <li>{bullet}</li>')
                        html.append('          </ul>')

                    html.append('        </div>')

        html.append('      </div>')

    return '\n'.join(html)


def update_index_html(resume_html):
    """Update the resume section in index.html"""
    with open('index.html', 'r', encoding='utf-8') as f:
        content = f.read()

    # Find and replace resume section
    pattern = r'<div class="resume-content">.*?</div>\s*</section><!-- End Resume Section -->'
    replacement = f'<div class="resume-content">\n{resume_html}\n    </div>\n    </section><!-- End Resume Section -->'

    updated_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(updated_content)

    print("✓ index.html updated with resume content")


def main():
    # Load credentials from environment
    creds_json = os.environ.get('GOOGLE_CREDENTIALS')
    if not creds_json:
        print("Error: GOOGLE_CREDENTIALS environment variable not set")
        return

    creds_info = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(creds_info, scopes=[
        'https://www.googleapis.com/auth/documents.readonly',
        'https://www.googleapis.com/auth/drive.readonly'  # Add this!
    ])

    doc_id = os.environ.get('GOOGLE_DOC_ID')
    if not doc_id:
        print("Error: GOOGLE_DOC_ID environment variable not set")
        return

    print("Fetching Google Doc...")
    doc = fetch_google_doc(doc_id, creds)

    print("Extracting resume data...")
    sections = extract_text_from_doc(doc)

    print("Downloading PDF...")
    pdf_path = 'assets/resume/Natalie_Olivo_Resume.pdf'
    download_pdf(doc_id, creds, pdf_path)

    print("Generating HTML...")
    resume_html = generate_resume_html(sections, include_contact=False)

    print("Updating index.html...")
    update_index_html(resume_html)

    print("\n✓ Resume updated successfully!")
    print(f"  - HTML updated in index.html")
    print(f"  - PDF saved to {pdf_path}")
    print(f"  - Phone/Email hidden from website display")


if __name__ == '__main__':
    main()


if __name__ == '__main__':
    main()
