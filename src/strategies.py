import os, sys
this_dir = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = '/'.join(this_dir.split('/')[:-1])
if PROJECT_DIR not in sys.path:
    sys.path.insert(1, PROJECT_DIR)

from pathlib import Path
from lxml import etree 
from typing import List, Tuple
# from PIL import Image 

from src.utils import detect_range, is_same_location, sha256_hash_str, sha256_hash_byte
from src.utils.date_util import get_dates_in_text
from src.utils.address_util import find_codepostal
from src.utils.pdf2xml import find_all_images_in_document, get_page_dimension, pdf_to_xml_tree,find_all_textboxes_B, \
                        find_all_images_in_xml


def export_to_my_xml(root, out_path):
    txt_blocks = find_all_textboxes_B(root)  # list of (bbox, [ (linebbox,linetxt) ])
    img_blocks = find_all_images_in_xml(root)  # [ (bbox, (W,H) ) ]
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


def contruct_block_html(line_list:List[Tuple]):
    """ Construct blocktext info


    Args:
    ---
        line_list (List[Tuple]): [(line_bbox, line_text, font_pos)]
            font_pos={"fontFamilyName$#size=XX$#color=(0,0,0)" : [positions]}
    Returns:
    ---
        list: [{type:"span/br", fontFamily:"", "size":"", "color":"", "text":""})]
    """
    html_content = []
    for line_bbox, line_text, font_pos in line_list:
        # in a line
        font_info_dict = {}
        for fontinfo, positions in font_pos.items():
            for _range in detect_range(positions):
                font_info_dict[_range] = fontinfo
        for k in sorted(font_info_dict.keys()):
            start = int(k[0])
            stop = int(k[1]) + 1
            font_info =  font_info_dict[k]
            parts = font_info.split("$#")
            fontname = ""
            size = ""
            color = ""
            for part in parts:
                if part.startswith("size="):
                    size = part.split("=")[1]
                elif part.startswith("color="):
                    color = part.split("=")[1]
                else:
                    fontname = part
            bboxstr = ",".join([str(b) for b in line_bbox])
            span = {"type":"span", "fontFamily":fontname, "size":size, "color":color, "bbox":bboxstr}
            span["text"] = "".join(line_text[start:stop])
            html_content.append(span)
        html_content.append({"type":"br"}) 
    return html_content


def text_end_with_postal_pattern(text):
    """Check if there is a codepostal_city at the end of the text"""
    list_cp_found = find_codepostal(text)
    if list_cp_found:
        cp,city = list_cp_found[-1]
        index_ = text.index(cp) + len(cp)
        tail = text[index_:].strip()
        if len(tail.replace("-"," ").split()) <= len(city.replace("-"," ").split()) + 2:
            return True
    return False


def get_position_key(bbox):
    """ Generate key for bbox using x0, y1. (rounded by 10)

    Args:
    ---
        bbox (tuple[float] or str): x0,y0,x1,y1
    Returns:
    ---
        str: "x0_y1"
    """
    if isinstance(bbox,str):
        bbox = [float(b) for b in bbox.split(",")]
    x0,_,_,y1  = bbox
    x0 = int(round(x0,-1))
    y1 = int(round(y1,-1))
    return f"{x0}_{y1}"


def main(inputdir:str, output_dir:str):
    """ Main app
    """
    in_dir = Path(inputdir)

    # dictionnaries
    inverse_index = {}  # block_hash -> {docid: [bbox_str]}
    img_inverse_index = {}  # img_hash -> {docid: [bbox_str]}
    collection_dict = {}  # docid -> {page_dim: (W,H), bbox_str : blocktext}
    collection_img_dict = {}   # {docid -> {bbox_str -> (width, height, bytehash)}}
    position_hash_dict = {}  # {"x0_y0" -> [hash_ids]}    used with get_position_key()

    # type of box
    block_with_page = set()  # {block_hash} of block with "page" in text
    block_with_date = set()  # {block_hash} of block with some dates in text
    block_with_address = set()  # {block_hash} of block with codepostal_city an the end of text


    for path in in_dir.glob("*.pdf"):
        docid = path.stem
        # print("DOCUMENT ::", docid)
        path_str = path.as_posix()
        root = pdf_to_xml_tree(path_str)
        txt_blocks = find_all_textboxes_B(root)  # list of (bbox, [ (linebbox,linetxt) ])
        img_blocks = find_all_images_in_document(path_str,first_page=True)  # [ LTImage ]
        if img_blocks:
            img_blocks = img_blocks[0]  #
        collection_img_dict[docid] = {}  
        
        # --- browse each image block in this document
        for img in img_blocks:
            bbox_str = ",".join([str(i) for i in img.bbox])
            img_stream = img.stream.get_data()
            hash_ = sha256_hash_byte(img_stream)
            # img_ext = determine_image_type(img_stream)
            outpath = Path(output_dir) / f"{hash_}.jpg"
            if not outpath.exists():
                with open(outpath,"wb") as f:
                    f.write(img_stream)
            collection_img_dict[docid][bbox_str] = (img.width,img.height,hash_)
            if hash_ in img_inverse_index:
                docpos_dict = img_inverse_index[hash_]
                if docid in docpos_dict:
                    docpos_dict[docid].append(bbox_str)
                else:
                    docpos_dict[docid] = [bbox_str]
            else:
                img_inverse_index[hash_] = {docid: [bbox_str]}

        pageW,pageH = get_page_dimension(root)
        collection_dict[docid] = {"page_dim":(int(pageW),int(pageH))}
        # -- browse each text block
        for b_bbox, linelist in txt_blocks:
            bbox_str = ",".join([str(i) for i in b_bbox])
            box_text = "\n".join("".join(line[1]) for line in linelist)
            box_text_words = box_text.split()
            # ----- make collection_dict
            collection_dict[docid][bbox_str] = contruct_block_html(linelist)
            # ---------------------------
            # ----- make inverse_index
            txt_hash = sha256_hash_str(box_text)
            if txt_hash in inverse_index:
                docpos_dict = inverse_index[txt_hash]
                if docid in docpos_dict:
                    docpos_dict[docid].append(bbox_str)
                else:
                    docpos_dict[docid] = [bbox_str]
            else:
                inverse_index[txt_hash] = {docid: [bbox_str]}
            
            # ---- make position_hash_dict
            poskey = get_position_key(b_bbox)
            if poskey in position_hash_dict:
                position_hash_dict[poskey].append(txt_hash)
            else:
                position_hash_dict[poskey] = [txt_hash]

            # ---------------------------
            # --- looking for blocks : "page x"
            if 1 < len(box_text_words) < 5 and "page" in box_text.lower():
                block_with_page.add(txt_hash)
            # --- looking for blocks : "date"
            elif 3 < len(box_text_words) < 10 and get_dates_in_text(box_text.lower()):
                block_with_date.add(txt_hash)
            if text_end_with_postal_pattern(box_text):
                block_with_address.add(txt_hash)
                # print("adress found")
            # --------------------------------------
            
    
    corpus_len = len(collection_dict)
    universal_hashes_ = set()  # hashids that repeat in all doc
    repeated_hashes = set()  # hashids that repeat in more than 1
    

    # check repeated text blocks
    for hashid,docs in inverse_index.items():
        if len(docs)==corpus_len:
            universal_hashes_.add(hashid)
        elif len(docs) > 1:
            repeated_hashes.add(hashid)
    # repeated images blocks
    for hashid,docs in img_inverse_index.items():
        if len(docs)==corpus_len:
            universal_hashes_.add(hashid)
        elif len(docs) > 1:
            repeated_hashes.add(hashid)

    uniques_hashes = [hid for hid in inverse_index if hid not in universal_hashes_ and hid not in repeated_hashes]
    
    # --- check if each universal_hash has the same bbox across docs
    universal_hashes_same_position = set()
    for hashid in universal_hashes_:
        pos_dict = {}
        if hashid in inverse_index:
            pos_dict = inverse_index[hashid]
        else:
            pos_dict = img_inverse_index[hashid]
        # supposing that a hashId occurs only 1 time in each doc
        bbox_list = [b[0] for b in pos_dict.values()]
        if is_same_location(bbox_list):
            universal_hashes_same_position.add(hashid)

    # --- using position_hash_dict to get boxes on the "same" location accross docs
    # -- get first address_box
    addr_blocks_same_location = set()
    if block_with_address:
        samplehash = list(block_with_address)[0]
        bbox_str = list(inverse_index[samplehash].values())[0][0]
        poskey = get_position_key(bbox_str)
        same_pos_blocks = position_hash_dict[poskey]
        addr_blocks_same_location = set(same_pos_blocks).intersection(block_with_address)
            
    
    
    # ----------------------------------------------------------
    # make xml
    page_node = etree.Element('page')
    univ_block_node = etree.SubElement(page_node,"universal_blocks")
    for hashid in universal_hashes_:
        pos_dict = {}
        same_location = hashid in universal_hashes_same_position
        if hashid in img_inverse_index:
            type_ = "img"
            pos_dict = img_inverse_index[hashid]
        else:
            pos_dict = inverse_index[hashid]  # {docid: [bbox]}
        
        bbox_str_ = list(pos_dict.values())[0][0]
        bbox_str = bbox_str_
        type_ = "unk"
        if hashid in block_with_date:
            type_ = "date"
        elif hashid in block_with_page:
            type_ = "pagination"
        if not same_location:
            bbox_str = ""
        if hashid in img_inverse_index:
            type_ = "img"
            blocknode = etree.SubElement(univ_block_node,"image", fixedLocation=str(same_location).lower(), 
                                        type=type_, bbox=bbox_str)
            blocknode.text = hashid  # img filename
        else:
            blocknode = etree.SubElement(univ_block_node,"textblock", fixedLocation=str(same_location).lower(), 
                                        type=type_, bbox=bbox_str)
            docid = list(pos_dict.keys())[0]
            for tag in collection_dict[docid][bbox_str_]:
                if tag["type"] == "br":
                    br_node = etree.SubElement(blocknode,"br")
                else:  # type = span
                    span_node = etree.SubElement(blocknode,"span", fontFamily=tag["fontFamily"], size=tag["size"], 
                                            color=tag["color"], bbox=tag["bbox"])
                    span_node.text = tag["text"]
    
    # --
    if len(addr_blocks_same_location) / corpus_len > 3/4:
        # number of blocks with address and on same location is >= 3/4 of collections
        samplehash = list(addr_blocks_same_location)[0]
        bbox_str = list(inverse_index[samplehash].values())[0][0]
        blocknode = etree.SubElement(univ_block_node,"textblock", fixedLocation="true", 
                    type="address", bbox=bbox_str)

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
    indir = "/home/jean/myriad/projects/poc/migration_ccm/data/sample"
    outdir = "/home/jean/myriad/projects/poc/migration_ccm/data/sample_output"
    out_xml_str = main(indir, outdir)
    with open(outdir+ "/struct.xml","wb") as f:
        f.write(out_xml_str)
    