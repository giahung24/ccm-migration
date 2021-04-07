from io import BytesIO, StringIO
from pathlib import Path

from pdfminer.converter import (HTMLConverter, PDFPageAggregator,
                                TextConverter, XMLConverter)
from pdfminer.layout import LAParams
from pdfminer.pdfdevice import PDFDevice
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import PDFPageInterpreter, PDFResourceManager
from pdfminer.pdfpage import PDFPage, PDFTextExtractionNotAllowed
from pdfminer.pdfparser import PDFParser
from pdfminer.high_level import extract_text_to_fp

from lxml import etree


def _pdf_to_string(path, format='xml', password=''):
    rsrcmgr = PDFResourceManager()
    out_stream = BytesIO()
    laparams = LAParams()
    if format == 'text':
        device = TextConverter(rsrcmgr, out_stream, laparams=laparams)
    elif format == 'html':
        device = HTMLConverter(rsrcmgr, out_stream, laparams=laparams)
    elif format == 'xml':
        device = XMLConverter(rsrcmgr, out_stream, laparams=laparams)
    else:
        raise ValueError('provide format, either text, html or xml!')
    fp = open(path, 'rb')
    interpreter = PDFPageInterpreter(rsrcmgr, device)
    maxpages = 0
    caching = True
    pagenos=set()
    for page in PDFPage.get_pages(fp, pagenos, maxpages=maxpages, password=password,caching=caching, check_extractable=True):
        interpreter.process_page(page)

    fp.close()
    device.close()

    text = out_stream.getvalue().decode("utf-8")
    out_stream.close()
    return text


def _pdf_to_pages(path):
    """ Get object (page, line, text, ...) in PDF

    Args:
        path (str)

    Returns:
        dict: []
    """
    fp = open(path, 'rb')
    # Create a PDF parser object associated with the file object.
    parser = PDFParser(fp)
    # Create a PDF document object that stores the document structure.
    # Supply the password for initialization.
    document = PDFDocument(parser)
    # Check if the document allows text extraction. If not, abort.
    if not document.is_extractable:
        raise PDFTextExtractionNotAllowed
    # Create a PDF resource manager object that stores shared resources.
    rsrcmgr = PDFResourceManager()
    # Set parameters for analysis.
    laparams = LAParams()
    # Create a PDF page aggregator object.
    device = PDFPageAggregator(rsrcmgr, laparams=laparams)
    interpreter = PDFPageInterpreter(rsrcmgr, device)
    i = 0
    dic = {}
    for page in PDFPage.get_pages(fp):
        interpreter.process_page(page)
        # receive the LTPage object for the page.
        layout = device.get_result()
        dic[i] = layout
        i = i + 1
    return dic


def pdf_to_xml_tree(path:str):
    """ Return lxml etree object"""
    string = _pdf_to_string(path)
    tree = etree.fromstring(string.encode("utf-8"))
    return tree


if __name__ == "__main__":
    in_dir = Path("/home/jean/myriad/projects/poc/migration_ccm/data/sample")
    for path in in_dir.glob("A511000000608_000006.pdf"):
        path = path.as_posix()
        # xmlstr = _pdf_to_string(path)


        tree = pdf_to_xml_tree(path)
        xmlstr=etree.tostring(tree, pretty_print=True).decode()


        with open(path+".xml","w") as f:
            f.write(xmlstr)
