import fitz
import sys


def extract_text_from_pdf(pdf_path):
    # Open the specified PDF file
    document = fitz.open(pdf_path)
    text = ""

    # Iterate through the pages
    for page_num in range(len(document)):
        page = document.load_page(page_num)  # loads the specified page
        text += page.get_text()  # extract text from the page

    return text


if __name__ == "__main__":
    pdf_path = sys.argv[1]
    extracted_text = extract_text_from_pdf(pdf_path)
    print(extracted_text)
