import os, sys
this_dir = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = '/'.join(this_dir.split('/')[:-1])
if PROJECT_DIR not in sys.path:
    sys.path.insert(1, PROJECT_DIR)

from pathlib import Path
from lxml import etree 

from src.utils import sha256_hash
from src.date_util import get_dates_in_text
from src.pdf2xml import pdf_to_xml_tree,find_all_textboxes_B, \
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


def main(inputdir:str):
    """[summary]
    """
    in_dir = Path(inputdir)
    inverse_index = {}  # block_hash -> {docid: [bbox_str]}
    collection_dict = {}  # docid -> {bbox_str : blocktext}

    block_with_page = set()  # {block_hash} of block with "page" in text
    block_with_date = set()  # {block_hash} of block with some dates in text

    for path in in_dir.glob("*.pdf"):
        docid = path.stem

        path_str = path.as_posix()
        root = pdf_to_xml_tree(path_str)
        txt_blocks = find_all_textboxes_B(root)  # list of (bbox, [ (linebbox,linetxt) ])
        # img_blocks = find_all_images(root)  # [ (bbox, (W,H) ) ]
        for b_bbox, linelist in txt_blocks:
            bbox_str = ",".join([str(i) for i in b_bbox])
            box_text = "\n".join(line[1] for line in linelist)
            box_text_words = box_text.split()

            if docid in collection_dict:
                collection_dict[docid][bbox_str] = box_text
            else:
                collection_dict[docid] = {bbox_str:box_text}

            txt_hash = sha256_hash(box_text)
            if txt_hash in inverse_index:
                docpos_dict = inverse_index[txt_hash]
                if docid in docpos_dict:
                    docpos_dict[docid].append(b_bbox)
                else:
                    docpos_dict[docid] = [b_bbox]
            else:
                inverse_index[txt_hash] = {docid: [b_bbox]}

            # check "page"
            if 1 < len(box_text_words) < 5 and "page" in box_text.lower():
                block_with_page.add(txt_hash)
            elif 3 < len(box_text_words) < 10 and get_dates_in_text(box_text.lower()):
                block_with_date.add(txt_hash)
            
    
    corpus_len = len(collection_dict)
    universal_hashes = set()  # hashids that repeat in all doc
    repeated_hashes = set()  # hashids that repeat in more than 1

    for hashid,docs in inverse_index.items():
        if len(docs)==corpus_len:
            universal_hashes.add(hashid)
        elif len(docs) > 1:
            repeated_hashes.add(hashid)
    
    uniques_hashes = [hid for hid in inverse_index if hid not in universal_hashes and hid not in repeated_hashes]

    # looking for blocks : "date" , "page x", "name address"




    return




if __name__ == "__main__":
    main("/home/jean/myriad/projects/poc/migration_ccm/data/sample")
   
    