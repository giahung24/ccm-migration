
import os, sys

this_dir = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = '/'.join(this_dir.split('/')[:-1])
if PROJECT_DIR not in sys.path:
    sys.path.insert(1, PROJECT_DIR)


from typing import List, Tuple
import hashlib




def convert_bbox_y(page_h, bbox) -> Tuple[float]:
    """ Bbox of pdfminer is bottom_base (y=0 at bottom), this function convert to y=0 at top as used in image.

    Args:
    ---
        page_h (float): page height
        bbox (tuple): (x0,y0,x1,y1)
    """
    (x0,y0,x1,y1) = bbox
    return (float(x0),page_h-float(y0),float(x1),page_h-float(y1))

def _union_bbox(box_left,box_right):
    """Unify 2boxes, keep the bigger dimensions"""
    (x0,y0,x1,y1) = box_left
    (xx0,yy0,xx1,yy1) = box_right
    return min(x0,xx0),min(y0,yy0),max(x1,xx1), max(y1,yy1)

def _update_column_with_new_letter(column, new_box):
    (col_x0,_,col_x1,_),_ = column
    (txt_x0,_,txt_x1,_),txt = new_box
    if (txt_x0 - col_x1) > 0.2*(txt_x1 - txt_x0):
        column[1] += " "
    column[1] += txt
    # --
    column[0] = _union_bbox(column[0],new_box[0])
    return column

def _is_overlap_y(boxleft, boxright):
    (x0_l,y0_l,x1_l,y1_l) = boxleft  # left
    (x0_r,y0_r,x1_r,y1_r) = boxright  # right
    if x0_l > x0_r:
        (x0_l,y0_l,x1_l,y1_l) = boxright
        (x0_r,y0_r,x1_r,y1_r) = boxleft
    return x0_r <= x1_l <= x1_r

def _is_column_gap(boxleft, boxright, ratio=3):
    """ Check if X_gap(boxright,boxleft) >= ratio*boxright_H"""
    (x0_l,y0_l,x1_l,y1_l) = boxleft  # left
    (x0_r,y0_r,x1_r,y1_r) = boxright  # right
    if x0_l > x0_r:
        (x0_l,y0_l,x1_l,y1_l) = boxright
        (x0_r,y0_r,x1_r,y1_r) = boxleft
    return (x0_r - x1_l) >= ratio * (y1_r - y0_r)


def construct_lines_columns(character_nodes_list:List):
    """ Given list of character node (bbox,char) in a page, this function return text lines (and columns in each line), top-down ordered.

    Args:
    ---
        `character_nodes_list` (List): list of [(x0,y0,x1,y1),text]

    Return
    ---
        List[List[List[Tuple,str]]]: list of lines, each line=list of columns, a column=[bbox,text]
    """
    # group letters by baselines
    baseline_dict = {}  # {y0: node_list}
    for (x0,y0,x1,y1),text in character_nodes_list:
        if y0 in baseline_dict:
            baseline_dict[y0].append(((x0,y0,x1,y1),text))
        else:
            baseline_dict[y0] = [((x0,y0,x1,y1),text)]
    
    # merge letters in line into columns 
    for y0 in baseline_dict:
        char_list = baseline_dict[y0]  # list of (bbox,text)
        first_char_width = char_list[0][0][2]-char_list[0][0][0]
        columns = [list(char_list[0])]  # cols in line, each col: (bbox,text)
        for i in range(1,len(char_list)):
            col = columns[-1]
            if char_list[i][0][0] - char_list[i-1][0][2] > 5*first_char_width:
                columns.append(list(char_list[i]))
                col = columns[-1]
            else:
                _update_column_with_new_letter(col, char_list[i])
        baseline_dict[y0] = columns

    # merge hanging lines (like superscript, underscript)
    final_list = []
    baseline_list = list(baseline_dict.values())  # list of line, each line is a list of columns, a column = [bbox,text]
    baseline_list.sort(key=lambda x: -x[0][0][1])
    for i in range(len(baseline_list)):  # line ordered from top to bottom
        current_line = baseline_list[i]
        if len(current_line) == 1:  # only 1 column
            if i < len(baseline_list) - 1:
                if baseline_list[i+1][-1][0][1] < current_line[-1][0][1] < baseline_list[i+1][-1][0][3] and \
                    baseline_list[i+1][-1][0][2] - 1 < current_line[-1][0][0] < baseline_list[i+1][-1][0][2] + 4:
                        # ---- superscript
                        _update_column_with_new_letter(baseline_list[i+1][-1], current_line[-1])
                        continue # do not append to final_list             
            if i > 0:
                if baseline_list[i-1][-1][0][1] < current_line[-1][0][3] < baseline_list[i-1][-1][0][3] and \
                baseline_list[i-1][-1][0][2] - 1 < current_line[-1][0][0] < baseline_list[i-1][-1][0][2] + 4:
                    # --- underscript
                    _update_column_with_new_letter(baseline_list[i-1][-1], current_line[-1])
                    continue  # do not append to final_list    
        final_list.append(current_line)
    return final_list


def grouping_text(character_nodes_list:List, line_gap_r=2.5, col_gap_r=3):
    """ Given a list-like of char_node (bbox,str), try to detect different textboxes   
    1. Split blocks by Y -> block_i
    2. For each block_i, split by X -> block_ij

    Args:
    ---
        character_nodes_list (list): list of xml <text> node
        line_gap_r (int): R * lineheight = min gap between two lines to be in the same block.
        col_gap_r (int): R * lineheight = min gap between two column to be in the same block. 
    
    Return:
    ---                 
        blocks_list (list): [(bbox, line_list)]. line=(bbox, txt)  ; top-down ordered
    """
    lines_col_list = construct_lines_columns(character_nodes_list)
    big_dict = {}  # {(lineid,colid):(bbox,txt)}
    final_blocks = {}  # {blockid: (bbox, lineid_list)}
    
    if lines_col_list:
        line_blocks = {}  # blocks by Y
        block_id = 0
        last_y0 = lines_col_list[0][0][0][1]  # first y0 of first line

        lineid = 0
        for line in lines_col_list:  # lines_col_list must be top_down ordered
            colid = 0
            for col in line: # [(bbox,txt)]
                big_dict[(lineid,colid)] = tuple(col)  # update line_col_id 
                # split blocks
                currentline_y0 = col[0][1]
                currentline_height = col[0][3] - col[0][1]
                if (last_y0 - currentline_y0) > line_gap_r * currentline_height:
                    block_id += 1   # new block
                if block_id in line_blocks:
                    line_blocks[block_id].append((lineid,colid))
                else:
                    line_blocks[block_id] = [(lineid,colid)]
                last_y0 = currentline_y0
                colid+=1
            lineid+=1
        # ----------- Done split by Y --------

        final_bid = 0
        for bid in line_blocks:  # for each big_line_block
            line_id_list = line_blocks[bid]  # (lineid,colid)
            # sort line by x0
            line_id_list.sort(key=lambda lineid: big_dict[lineid][0][0])

            first_line = line_id_list[0]
            first_line_bbox = big_dict[first_line][0]
            col_blocks_bbox = {0:first_line_bbox}  # {block_i: bbox_i}
            col_blocks_lid = {0:[first_line]}
            # --- attempt to split column blocks
            for i in range(1, len(line_id_list)):  
                lineid = line_id_list[i]
                line_bbox = big_dict[lineid][0]

                new_block = True
                for colblock_id in col_blocks_bbox:  # check if current line is belong to an existing colblock
                    block_bbox = col_blocks_bbox[colblock_id]
                    # check if current line is "belong" to this block.
                    if _is_overlap_y(line_bbox, block_bbox) or not _is_column_gap(block_bbox,line_bbox,col_gap_r):
                        col_blocks_bbox[colblock_id] = _union_bbox(block_bbox,line_bbox)
                        col_blocks_lid[colblock_id].append(lineid)
                        new_block = False
                        break
                if new_block:
                    col_blocks_bbox[colblock_id+1] = line_bbox
                    col_blocks_lid[colblock_id+1] = [lineid]
            # --- update column blocks to final blocks
            for col_i in range(len(col_blocks_lid)):
                final_bid += col_i
                final_blocks[final_bid] = (col_blocks_bbox[col_i],col_blocks_lid[col_i])
            final_bid += 1
    

    block_list = []
    for bid in final_blocks:
        line_list = []
        bbox, lid_list = final_blocks[bid]
        for lid in lid_list:
            line_bbox,txt = big_dict[lid]
            line_list.append((line_bbox,txt))
        block_list.append((bbox,line_list))

    return block_list


def sha256_hash(input_string):
    """ Hash a string into 64 char hash"""
    return hashlib.sha256(input_string.encode()).hexdigest()