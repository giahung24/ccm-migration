#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import division

from flask import Flask, jsonify, request, send_file
from pathlib import Path
from lxml import etree 

import sys
import os
import time
import tempfile
import traceback
import io
import shutil
import zipfile

this_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = '/'.join(this_dir.split('/')[:-1])
if project_dir not in sys.path:
    sys.path.insert(1, project_dir)

from src.utils.pdf2xml import find_all_images_in_document, find_all_textboxes_B, pdf_to_xml_tree
from src.strategies import export_to_my_xml


HEADERS = {'Content-type': 'application/json', 'Accept': 'text/plain'}




def flask_app():
    app_ = Flask(__name__)

    @app_.route('/', methods=['GET'])
    def server_is_up():
        status = {"status":"ok", "message":"Greeting from Myriad!"}
        return jsonify(status)


    @app_.route('/pdf2xml', methods=['POST'])
    def export_xml_from_pdf():
        """ 
        Returns
        -------
            zip
        """
        # to_predict = request.json
        if not 'pdf_file' in request.files:
            return jsonify({'error': 'no PDF file','desc':'PDF file must be provided with \'pdf_file\' parameter'}), 400

        pdf_file = request.files.get('pdf_file')
        pdf_data = pdf_file.read()
        if not pdf_data:
            return jsonify({'error': 'no PDF file','desc':'PDF file is empty'}), 400

        pdf_name_org = pdf_file.filename
        timestamp = str(int(time.time()))
        pdf_name = timestamp+"_"+pdf_name_org
        tmpdir = Path(tempfile.gettempdir()) / ("ccm_" + timestamp)
        if not tmpdir.exists():
            tmpdir.mkdir(parents=True, exist_ok=True)
        output_dir = tmpdir / "output"
        if not output_dir.exists():
            output_dir.mkdir(parents=True, exist_ok=True)
        
        # -- save pdf to disk
        pdf_path:Path = tmpdir / pdf_name
        with pdf_path.open("wb") as f:
            f.write(pdf_data)
        
        # --- save pdfminer_xml
        root = pdf_to_xml_tree(pdf_path.as_posix())
        pdfminer_xml_path = output_dir / (pdf_name_org[:-4]+".raw.xml")
        doc = etree.ElementTree(root)
        etree.indent(doc, space="    ")
        with open(pdfminer_xml_path, 'wb') as outFile:
            doc.write(outFile, xml_declaration=True, encoding='utf-8',pretty_print=True)

        # --- save my xml
        my_xml_path = output_dir / (pdf_name_org[:-4]+".blocks.xml")
        txt_blocks = find_all_textboxes_B(root)  # list of (bbox, [ (linebbox,linetxt) ])
        img_blocks = find_all_images_in_document(pdf_path.as_posix(),first_page=True)  # [ LTImage ]
        if img_blocks:
            img_blocks = img_blocks[0]  #
        export_to_my_xml(txt_blocks, img_blocks, my_xml_path)

        # --- zip output folder
        data = io.BytesIO()
        with zipfile.ZipFile(data, mode='w') as z:

            z.write(my_xml_path,my_xml_path.name)
            z.write(pdfminer_xml_path,pdfminer_xml_path.name)
        data.seek(0)

        # --- delete temp dir
        try:
            shutil.rmtree(tmpdir.as_posix())
        except:
            traceback.print_exc()


        return send_file(
            data,
            mimetype='application/zip',
            as_attachment=True,
            download_name='results.zip'
        )


    return app_


if __name__ == '__main__':
    # print(sys.path)
    app = flask_app()
    app.run(debug=True, host='0.0.0.0')
    print("Server started. Listening....")
