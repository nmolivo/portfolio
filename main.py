import json
import os
import re
from datetime import datetime
from urllib.request import urlopen

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


def fetch_google_doc(doc_id, creds):
    """Fetch Google Doc content using Docs API"""
    service = build('docs', 'v1', credentials=creds)
    doc = service.documents().get(documentId=doc_id).execute()
    return doc


def extract_text_from_doc(doc_content):
    """Extract all text and structure from Google Doc"""
    sections = {}
    current_section = None
    current_list = []

    for element in doc_content.get('body', {}).get('content', []):
        if 'paragraph' in element:
            paragraph = element.get('paragraph', {})

            # Get all text in this paragraph
            text_parts = []
            for run in paragraph.get('elements', []):
                if 'textRun' in run:
                    text_parts.append(run['textRun'].get('content', ''))

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
                else:
                    if current_section and current_list:
                        sections[current_section] = current_list
                        current_list = []
                    sections[text] = None

    return sections


def download_pdf(doc_id, creds, output_path):
    """Download Google Doc as PDF"""
    try:
        # Refresh credentials if needed
        creds.refresh(Request())

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
    """Generate resume HTML from extracted sections"""
    html = []
    html.append('      <!-- Contact Info -->')
    html.append('      <div class="contact-info-box">')
    html.append('        <h4>Contact Information</h4>')

    if include_contact:
        html.append(
            '        <p><i class="bi bi-envelope"></i> nmolivo@gmail.com</p>')
        html.append(
            '        <p><i class="bi bi-telephone"></i> +34 604 81 43 03</p>')
    else:
        # Only show location and citizenship (hide email/phone on website)
        pass

    html.append('        <p><i class="bi bi-geo-alt"></i> Alicante, Spain</p>')
    html.append('        <p><i class="bi bi-check-circle"></i> US Citizen</p>')
    html.append('      </div>')
    html.append('')

    # Map section names to HTML
    section_mapping = {
        'Professional Summary': ('person-badge', 'Professional Summary'),
        'Core Technical Skills': ('gear', 'Core Technical Skills'),
        'Professional Experience': ('briefcase', 'Professional Experience'),
        'Projects': ('code-square', 'Featured Projects'),
        'Certifications': ('award', 'Certifications'),
        'Education & Training': ('book', 'Education & Training'),
        'Awards & Recognition': ('star', 'Awards & Recognition'),
        'Early Career Experience': ('clock-history', 'Early Career Experience'),
    }

    for section_name, (icon, display_name) in section_mapping.items():
        if section_name not in sections:
            continue

        content = sections[section_name]

        # Professional Summary - just text
        if section_name == 'Professional Summary':
            html.append('      <!-- Professional Summary -->')
            html.append('      <div class="resume-section">')
            html.append(
                f'        <h3 class="resume-title"><i class="bi bi-{icon}"></i> {display_name}</h3>')
            if isinstance(content, list):
                for item in content:
                    html.append(f'        <p>{item}</p>')
            else:
                html.append(f'        <p>{content}</p>')
            html.append('      </div>')

        # Skills - special formatting
        elif section_name == 'Core Technical Skills':
            html.append('      <!-- Core Technical Skills -->')
            html.append('      <div class="resume-section">')
            html.append(
                f'        <h3 class="resume-title"><i class="bi bi-{icon}"></i> {display_name}</h3>')
            html.append('        <div class="skills-container">')
            if isinstance(content, list):
                for item in content:
                    # Parse "Category: skill1, skill2, skill3"
                    if ':' in item:
                        category, skills = item.split(':', 1)
                        category = category.strip()
                        skills = [s.strip() for s in skills.split(',')]
                        html.append('          <div class="skill-category">')
                        html.append(f'            <h5>{category}</h5>')
                        html.append('            <div class="skill-tags">')
                        for skill in skills:
                            html.append(
                                f'              <span class="badge">{skill}</span>')
                        html.append('            </div>')
                        html.append('          </div>')
            html.append('        </div>')
            html.append('      </div>')

        # Awards - simple list
        elif section_name == 'Awards & Recognition':
            html.append('      <!-- Awards & Recognition -->')
            html.append('      <div class="resume-section">')
            html.append(
                f'        <h3 class="resume-title"><i class="bi bi-{icon}"></i> {display_name}</h3>')
            html.append('        <ul class="awards-list">')
            if isinstance(content, list):
                for item in content:
                    html.append(f'          <li>{item}</li>')
            html.append('        </ul>')
            html.append('      </div>')

        # Experience & Education - items with details
        else:
            html.append(f'      <!-- {display_name} -->')
            html.append('      <div class="resume-section">')
            html.append(
                f'        <h3 class="resume-title"><i class="bi bi-{icon}"></i> {display_name}</h3>')
            if isinstance(content, list):
                i = 0
                while i < len(content):
                    item = content[i]
                    html.append('        <div class="resume-item">')
                    html.append(f'          <h4>{item}</h4>')
                    i += 1

                    # Next items are details (company, dates, description)
                    if i < len(content):
                        html.append(f'          <h5>{content[i]}</h5>')
                        i += 1

                    if i < len(content):
                        html.append(f'          <p><em>{content[i]}</em></p>')
                        i += 1

                    # Collect bullet points
                    bullets = []
                    while i < len(content) and not content[i].endswith(':') and not any(c.isupper() for c in content[i].split()[0:1]):
                        bullets.append(content[i])
                        i += 1

                    if bullets:
                        html.append('          <ul>')
                        for bullet in bullets:
                            html.append(f'            <li>{bullet}</li>')
                        html.append('          </ul>')

                    html.append('        </div>')
            html.append('      </div>')

    # Download button
    html.append('      <!-- PDF Download -->')
    html.append('      <div class="resume-download">')
    html.append(
        '        <a href="/assets/resume/Natalie_Olivo_Resume.pdf" class="btn btn-primary" download>')
    html.append('          <i class="bi bi-download"></i> Download PDF Resume')
    html.append('        </a>')
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
    creds = Credentials.from_authorized_user_info(creds_info)

    doc_id = os.environ.get('DOC_ID')
    if not doc_id:
        print("Error: DOC_ID environment variable not set")
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
