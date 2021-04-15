import os, sys

this_dir = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = '/'.join(this_dir.split('/')[:-1])
if PROJECT_DIR not in sys.path:
    sys.path.insert(1, PROJECT_DIR)

from io import BytesIO, StringIO
from pathlib import Path

from pdfminer.converter import (HTMLConverter, PDFPageAggregator,
                                TextConverter, XMLConverter)
from pdfminer.layout import LAParams
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import PDFPageInterpreter, PDFResourceManager
from pdfminer.pdfpage import PDFPage, PDFTextExtractionNotAllowed
from pdfminer.pdfparser import PDFParser
from lxml import etree

from src.utils import grouping_text


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
    """ Read pdf file and return lxml etree object"""
    string = _pdf_to_string(path)
    tree = etree.fromstring(string.encode("utf-8"))
    return tree


def get_bbox(node):
    """(x0,y0,x1,y1)"""
    if "bbox" in node.attrib:
        return tuple(map(float,node.attrib["bbox"].split(",")))
    return None


def get_page_dimension(root, pageno=1):
    """ Get page width, page height

    Args:
    ---
        root (etree): root node
        pageno (int, optional): Page num in document. Defaults to 1.

    Returns:
    ---
        tuple or None: pageW, pageH
    """
    page_i = pageno - 1
    bbox = get_bbox(root[page_i])
    if bbox:
        _, _, pageW, pageH = bbox
        return pageW, pageH
    


def find_all_tag_recursively(root, tag_name):
    """ Recursively get all <tag_name> nodes in document

    Args:
    ---
        root ([type]): [description]

    Returns:
    ---
        list: [nodes]
    """
    node_list = []
    for page in root:
        query = f'.//{tag_name}'
        node_list = page.findall(query)
        break  # currently support 1st page
    return node_list


def find_all_textnodes(root):
    """ Recursively get all <text> nodes in document

    Args:
    ---
        root ([type]): [description]

    Returns:
    ---
        list: [(bbox,text)]
    """
    return find_all_tag_recursively(root,"text")

def find_textnodes_in_figure(root):
    """ Get all <text> nodes in all <figure> tags

    Args:
    ---
        root ([type]): [description]

    Returns:
    ---
        list: [(bbox,text)]
    """
    character_nodes_list = []
    for page in root:
        # print(page)
        figures = page.findall("figure")
        for fig in figures:
            characters = fig.findall("text")
            character_nodes_list += [(get_bbox(ch),ch.text) for ch in characters if "bbox" in ch.attrib]
        break # currently support 1st page
    return character_nodes_list

def find_all_textbox_nodes(root):
    """ Get all <textbox> in document
    Args:
    ---
        root (etree): xml root

    Returns:
    ---
        list: list of (bbox, line_list); line=(bbox,txt)
    """
    block_list = []  # list of (bbox, line_list); line=(bbox,txt)
    for page in root:
        textboxes = page.findall("textbox")
        for i,textbox in enumerate(textboxes):
            if "bbox" in textbox.attrib:
                block_bbox = get_bbox(textbox)
                block_lines = []
                for textline in textbox:
                    if "bbox" in textline.attrib:
                        linebbox = get_bbox(textline)
                        linetext = "".join(textline.itertext()).replace("\n","")
                        block_lines.append((linebbox,linetext))
                block_list.append((block_bbox,block_lines))
        break  # 1st page only
    return block_list


def find_all_images(root):
    """
    Return
    ---
        list of (bbox,(W,H))
    """
    img_list = []  # list of (bbox,(W,H))
    img_tags = find_all_tag_recursively(root,"image")
    for img in img_tags:
        parent_node = img.getparent()
        size = (int(img.attrib["width"]),int(img.attrib["height"]))
        bbox = None
        # print(f'image size: {img.attrib["width"]}x{img.attrib["height"]}',)
        if parent_node is not None:
            bbox = get_bbox(parent_node)
        img_list.append((bbox,size))
    return img_list


def find_all_textboxes_A(root):
    """ Simply get all <text> in document, then group into blocks

    Args:
    ---
        root (etree): lxml root

    Return:
    ---
        blocks_list (list): [(bbox, line_list)]. line=(bbox, txt)
    """
    block_list = []  # list of (bbox, line_list). line=(bbox, txt)
    block_list = grouping_text(find_all_tag_recursively(root,"text"))
    return block_list


def find_all_textboxes_B(root):
    """ Get all <textbox> in document, then get all <text> in <figure> and group into blocks

    Args:
    ---
        root (etree): lxml root

    Return:
    ---
        blocks_list (list): [(bbox, line_list)]. line=(bbox, txt)
    """
    block_list = []  # list of (bbox, line_list). line=(bbox, txt)

    block_list = find_all_textbox_nodes(root)   # 1st list of blocks
    block_list += grouping_text(find_textnodes_in_figure(root)) # 2nd list of blocks
    block_list.sort(key=lambda block: -block[0][1])  # sort top-down
    return block_list