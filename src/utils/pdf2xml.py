import os, sys

this_dir = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = '/'.join(this_dir.split('/')[:-1])
if PROJECT_DIR not in sys.path:
    sys.path.insert(1, PROJECT_DIR)

from io import BytesIO, StringIO
from pathlib import Path
from typing import Dict, List

from pdfminer.converter import (HTMLConverter, PDFPageAggregator,
                                TextConverter, XMLConverter)
from pdfminer.layout import LAParams, LTFigure,LTPage,LTImage
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


def pdf_to_pages(path):
    """ Get object (page, line, text, ...) in PDF

    Args:
        path (str)

    Returns:
        list of pdfminer.layout.LTPage
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
    output = []
    for page in PDFPage.get_pages(fp):
        interpreter.process_page(page)
        # receive the LTPage object for the page.
        layout:LTPage = device.get_result()
        output.append(layout)
    return output


def pdf_to_xml_tree(path:str):
    """ Read pdf file and return lxml etree object"""
    string = _pdf_to_string(path)
    tree = etree.fromstring(string.encode("utf-8"))
    return tree


def get_attrib(node,_attrib):
    if _attrib in node.attrib:
        return node.attrib[_attrib]
    return None


def get_bbox(node):
    """(x0,y0,x1,y1)"""
    bbox = get_attrib(node,"bbox")
    if bbox:
        return tuple(map(float,bbox.split(",")))
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
   
def fontinfo_textnode(textnode:etree._Element):
    """ return fontinfo pattern: fontFamilyName$#size=XX$#color=(0,0,0)
    """
    fontname = ""  
    if "font" in textnode.attrib:
        fontname = get_attrib(textnode,"font")
        size = get_attrib(textnode,"size")
        color = get_attrib(textnode,"ncolour")
        if size:
            size = str(round(float(size)))
            fontname += "$#size="+size
        if color:
            if color == "0":
                color = "(0,0,0)"
            else:  # ncolour="(0.075, 0.424, 0.741)"
                color = [str(int(float(r)*255)) for r in color[1:-1].split(",")]   # convert to RGB 255 base
                color = ",".join(color)
                color = "("+ color + ")"
            fontname += "$#color=" + color
    return fontname

def get_text_with_fontinfo_in_linenode(line_node:etree._Element):
    """ 
    Args:
    ---
        line_node (_Element):
    Returns:
    ---
        list,dict: line_text, {font_name: [char positions]}
    """
    font_info = {}
    line_text = []
    fontname = ""
    for pos,textnode in enumerate(line_node):
        if "font" in textnode.attrib:
            # if len(textnode.text) > 1:
            #     print(textnode.text)
            line_text.append(textnode.text)
            fontname = get_attrib(textnode,"font")
            size = get_attrib(textnode,"size")
            color = get_attrib(textnode,"ncolour")
            if size:
                size = str(round(float(size)))
                fontname += "$#size="+size
            if color:
                if color == "0":
                    color = "(0,0,0)"
                else:  # ncolour="(0.075, 0.424, 0.741)"
                    color = [str(int(float(r)*255)) for r in color[1:-1].split(",")]   # convert to RGB 255 base
                    color = ",".join(color)
                    color = "("+ color + ")"
                fontname += "$#color=" + color

            if fontname in font_info:
                font_info[fontname].append(pos)
            else:
                font_info[fontname] = [pos]
        elif textnode.text == " ":
            line_text.append(textnode.text)
            if fontname in font_info:
                font_info[fontname].append(pos)

    return line_text, font_info

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
        list: [(bbox,text,fontname)]
    """
    characters = find_all_tag_recursively(root,"text")
    character_nodes_list = [(get_bbox(ch),ch.text,fontinfo_textnode(ch)) for ch in characters if "bbox" in ch.attrib ]
    return character_nodes_list


def find_textnodes_in_figure(root):
    """ Get all <text> nodes in all <figure> tags

    Args:
    ---
        root ([type]): [description]

    Returns:
    ---
        list: [(bbox,text,fontname)]
    """
    character_nodes_list = []
    for page in root:
        # print(page)
        figures = page.findall("figure")
        for fig in figures:
            characters = fig.findall("text")
            character_nodes_list += [(get_bbox(ch),ch.text,fontinfo_textnode(ch)) for ch in characters if "bbox" in ch.attrib]
        break # currently support 1st page
    return character_nodes_list


def find_all_textbox_nodes(root):
    """ Get all <textbox> in document
    Args:
    ---
        root (etree): xml root

    Returns:
    ---
        list: list of (bbox, line_list); line=(bbox,txt,font_info); font_info={fontname:[positions]}
    """
    block_list = []  # list of (bbox, line_list); line=(bbox,txt)
    for page in root:
        textboxes = page.findall("textbox")
        for i,textbox in enumerate(textboxes):
            if "bbox" in textbox.attrib:
                block_bbox = get_bbox(textbox)
                block_lines = []
                for linenode in textbox:
                    if "bbox" in linenode.attrib:
                        linebbox = get_bbox(linenode)
                        # linetext = "".join(textline.itertext()).replace("\n","")
                        linetext, font_info = get_text_with_fontinfo_in_linenode(linenode)
                        block_lines.append((linebbox,linetext,font_info)) 
                block_list.append((block_bbox,block_lines))
        break  # 1st page only
    return block_list


def find_all_textboxes_A(root):
    """ Simply get all <text> in document, then group into blocks

    Args:
    ---
        root (etree): lxml root

    Return:
    ---
        blocks_list (list): [(bbox, line_list)]. line=(bbox,txt,font_info); font_info={fontname:[positions]}
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
        blocks_list (list): [(bbox, line_list)]. line=(bbox, txt, fontinfo)
    """
    block_list = []  # list of (bbox, line_list). line=(bbox, txt)

    block_list = find_all_textbox_nodes(root)   # 1st list of blocks
    block_list += grouping_text(find_textnodes_in_figure(root)) # 2nd list of blocks
    block_list.sort(key=lambda block: -block[0][1])  # sort top-down
    return block_list



def find_all_images_in_xml(root):
    """
    Return
    ---
        list of (bbox,(W,H))
    """
    img_list = []  # list of (bbox,(W,H))
    img_tags = find_all_tag_recursively(root[0],"image")  # find in 1st page only
    for img in img_tags:
        parent_node = img.getparent()
        size = (int(img.attrib["width"]),int(img.attrib["height"]))
        bbox = None
        # print(f'image size: {img.attrib["width"]}x{img.attrib["height"]}',)
        if parent_node is not None:
            bbox = get_bbox(parent_node)
        img_list.append((bbox,size))
    return img_list


def find_all_images_in_page(page:LTPage):
    """

    Args:
    ---
        page (LTPage)

    Returns:
    ---
        list of LTImage
    """
    img_list = []
    parent = page
    if hasattr(parent,"_objs"):
        for obj in parent._objs:
            if isinstance(obj,LTImage):
                img_list.append(obj)
            elif isinstance(obj, LTFigure):
                img_list.extend(find_all_images_in_page(obj))
    return img_list


def find_all_images_in_document(path, first_page=False)->Dict[int,LTImage]:
    """ 
    """
    output_dict = {}
    page_list = pdf_to_pages(path)
    for i,page in enumerate(page_list):
        img_list = find_all_images_in_page(page)
        output_dict[i] = img_list
        if first_page:
            break
    return output_dict
