import os, sys

this_dir = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = '/'.join(this_dir.split('/')[:-1])
if PROJECT_DIR not in sys.path:
    sys.path.insert(1, PROJECT_DIR)

from src.pdf2xml import pdf_to_pages, pdf_to_xml_tree

if __name__ == "__main__":

    page_dict = pdf_to_pages('/home/jean/myriad/projects/poc/migration_ccm/data/sample/A511000000109_000001.pdf')
    a = 0