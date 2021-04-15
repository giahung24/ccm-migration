import os, sys
this_dir = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = '/'.join(this_dir.split('/')[:-1])
if PROJECT_DIR not in sys.path:
    sys.path.insert(1, PROJECT_DIR)

from pathlib import Path
from lxml import etree 
from typing import List
import numpy as np

from src.utils import sha256_hash
from src.date_util import get_dates_in_text
from src.pdf2xml import get_page_dimension, pdf_to_xml_tree,find_all_textboxes_B, \
                        find_all_images


def export_to_my_xml(root, out_path):
    txt_blocks = find_all_textboxes_B(root)  # list of (bbox, [ (linebbox,linetxt) ])
    img_blocks = find_all_images(root)  # [ (bbox, (W,H) ) ]
    page_node = etree.Element('page')
    txtblock_node = etree.SubElement(page_node,"textblocks")
    for b_bbox, linelist in txt_blocks:
        bbox_str = ",".join([str(i) for i in b_bbox])
        blocknode = etree.SubElement(txtblock_node,"textblock", bbox=bbox_str)
        for lbbox,linetxt in linelist:
            bbox_str = ",".join([str(i) for i in lbbox])
            linenode = etree.SubElement(blocknode,"textline",bbox=bbox_str)
            linenode.text = linetxt
    imgs_node = etree.SubElement(page_node,"images")
    for bbox, (W,H) in img_blocks:
        bbox_str = ",".join([str(i) for i in bbox])
        imgnode = etree.SubElement(imgs_node,"image", bbox=bbox_str, width=str(W), height=str(H))
    # Make a new document tree
    doc = etree.ElementTree(page_node)
    etree.indent(doc, space="    ")
    # outstr = etree.tostring(doc)
    # Save to XML file
    with open(out_path, 'wb') as outFile:
        doc.write(outFile, xml_declaration=True, encoding='utf-8',pretty_print=True)
        return 1
    return 0


def is_same_location(bbox_list:List):
    w_ratios = []  # list of (x0,width) in proportion to page_W
    h_ratios = []  # list of (y0,height) in proportion to page_H
    if bbox_list:
        if isinstance(bbox_list[0],str):
            bbox_list = [tuple(map(float,b.split(","))) for b in bbox_list]
    # for bbox in bbox_list:
    #     if isinstance(bbox,str):
    #         bbox_ = bbox.split(",")
    #         if len(bbox_) == 4:
    #             bbox = bbox_
    #     (x0,y0,x1,y1) = bbox
    a = np.std(bbox_list,axis=0)
    return np.mean(a) < 5  # 5 pixels of derivation on each dimension


def main(inputdir:str):
    """[summary]
    """
    in_dir = Path(inputdir)
    inverse_index = {}  # block_hash -> {docid: [bbox_str]}
    collection_dict = {}  # docid -> {page_dim: (W,H), bbox_str : blocktext}
    collection_img_dict = {}   # docid -> {bbox_str : (W,H)}

    block_with_page = set()  # {block_hash} of block with "page" in text
    block_with_date = set()  # {block_hash} of block with some dates in text



    for path in in_dir.glob("*.pdf"):
        docid = path.stem

        path_str = path.as_posix()
        root = pdf_to_xml_tree(path_str)
        txt_blocks = find_all_textboxes_B(root)  # list of (bbox, [ (linebbox,linetxt) ])
        img_blocks = find_all_images(root)  # [ (bbox, (W,H) ) ]
        collection_img_dict[docid] = {}
        for b_bbox, (W,H) in img_blocks:
            bbox_str = ",".join([str(i) for i in b_bbox])
            collection_img_dict[docid][bbox_str] = (W,H)  # TODO: get image content

        pageW,pageH = get_page_dimension(root)
        collection_dict[docid] = {"page_dim":(int(pageW),int(pageH))}
        # -- loop on each block, 
        for b_bbox, linelist in txt_blocks:
            bbox_str = ",".join([str(i) for i in b_bbox])
            box_text = "\n".join(line[1] for line in linelist)
            box_text_words = box_text.split()
            # ----- make collection_dict
            collection_dict[docid][bbox_str] = box_text
            # ---------------------------
            # ----- make inverse_index
            txt_hash = sha256_hash(box_text)
            if txt_hash in inverse_index:
                docpos_dict = inverse_index[txt_hash]
                if docid in docpos_dict:
                    docpos_dict[docid].append(bbox_str)
                else:
                    docpos_dict[docid] = [bbox_str]
            else:
                inverse_index[txt_hash] = {docid: [bbox_str]}
            # ---------------------------
            # --- looking for blocks : "page x"
            if 1 < len(box_text_words) < 5 and "page" in box_text.lower():
                block_with_page.add(txt_hash)
            # --- looking for blocks : "date"
            elif 3 < len(box_text_words) < 10 and get_dates_in_text(box_text.lower()):
                block_with_date.add(txt_hash)
            # TODO: looking for blocks "name, address"
            # --------------------------------------
            
    
    corpus_len = len(collection_dict)
    universal_hashes_ = set()  # hashids that repeat in all doc
    repeated_hashes = set()  # hashids that repeat in more than 1

    for hashid,docs in inverse_index.items():
        if len(docs)==corpus_len:
            universal_hashes_.add(hashid)
        elif len(docs) > 1:
            repeated_hashes.add(hashid)

    uniques_hashes = [hid for hid in inverse_index if hid not in universal_hashes_ and hid not in repeated_hashes]
    
    # --- check if each universal_hash has the same bbox across docs
    universal_hashes_same_position = set()
    for hashid in universal_hashes_:
        pos_dict = inverse_index[hashid]
        # supposing that a hashId occurs only 1 time in each doc
        bbox_list = [b[0] for b in pos_dict.values()]
        if is_same_location(bbox_list):
            universal_hashes_same_position.add(hashid)

    for hid in universal_hashes_:
        if hid not in universal_hashes_same_position:
            doc_dict = inverse_index[hid]
            docid = list(doc_dict.keys())[0]
            # for bbox in doc_dict[docid]:
            #     print(collection_dict[docid][bbox])
            #     print("------")

    # TODO: process images_block to check universal image
    # ----------------------------------------------------------
    # make xml
    page_node = etree.Element('page')
    univ_block_node = etree.SubElement(page_node,"universal_blocks")
    for hashid in universal_hashes_:
        pos_dict = inverse_index[hashid]  # {docid: [bbox]}
        same_location = hashid in universal_hashes_same_position
        bbox_str = list(pos_dict.values())[0][0]
        docid = list(pos_dict.keys())[0]
        block_text = collection_dict[docid][bbox_str]
        type_ = "unk"
        if hashid in block_with_date:
            type_ = "date"
        elif hashid in block_with_page:
            type_ = "page"
        if not same_location:
            bbox_str = ""
        blocknode= etree.SubElement(univ_block_node,"textblock", fixedLocation=str(same_location).lower(), 
                                    type=type_, bbox=bbox_str)
        blocknode.text = block_text
        
    # for bbox, (W,H) in img_blocks:
    #     bbox_str = ",".join([str(i) for i in bbox])
    #     imgnode = etree.SubElement(univ_block_node,"image", bbox=bbox_str, width=str(W), height=str(H))
    # Make a new document tree
    doc = etree.ElementTree(page_node)
    etree.indent(doc, space="    ")
    outstr = etree.tostring(doc)
    # Save to XML file
    # with open(out_path, 'wb') as outFile:
    #     doc.write(outFile, xml_declaration=True, encoding='utf-8',pretty_print=True)
    #     return 1
    # pass
    return outstr




if __name__ == "__main__":
    out_xml_str = main("/home/jean/myriad/projects/poc/migration_ccm/data/sample")
    with open("/home/jean/myriad/projects/poc/migration_ccm/data/sample/struct.xml","wb") as f:
        f.write(out_xml_str)
    