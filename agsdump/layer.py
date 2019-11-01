import os
import sld
import json
import base64
import requests
import lxml.etree
from slugify import slugify

class Layer(object):
    def __init__(self, service_url, layer_id, dump_folder=None):
        self.service_url = service_url
        self.layer_id = str(layer_id)
        self.sld_doc = sld.StyledLayerDescriptor()
        self._dump_folder = dump_folder

        self._renderers = {
            'simple': self._render_esriSimple,
            'uniqueValue': self._render_uniqueValue,
            'classBreaks': self._render_classBreaks,
        }

        self._type_converters = {
            'esriPMS': self._convert_esriPMS,
            'esriSFS': self._convert_esriSFS,
            'esriSLS': self._convert_esriSLS,
            'esriSMS': self._convert_esriSMS,
            'esriTS': self._convert_esriTS,
        }

        self._style_converters = {
            'esriSMSCircle': self._convert_esriSMSCircle,
            'esriSLSDash': self._convert_esriSLSDash,
            'esriSFSSolid': self._convert_esriSFSSolid,
            'esriSLSSolid': self._convert_esriSLSSolid,
        }

    @property
    def _url(self):
        return self.urljoin(self.service_url, self.layer_id)

    @property
    def dump_folder(self):
        if not self._dump_folder:
            dirpath = os.getcwd()
            self._dump_folder = os.path.join(dirpath, "style")

        if not os.path.exists(self._dump_folder):
            os.makedirs(self._dump_folder)

        return self._dump_folder

    @property
    def descriptor(self):
        params = {'f': 'json'}
        response = requests.get(self._url, params=params)
        return json.loads(response.text)

    @property
    def name(self):
        return slugify(self.descriptor.get('name')).replace("-", "-")

    @property
    def drawingInfo(self):
        return self.descriptor.get('drawingInfo')

    @property
    def geometryType(self):
        return self.descriptor.get('geometryType')

    @property
    def renderer(self):
        return self.descriptor.get('drawingInfo').get('renderer')

    @property
    def labelingInfo(self):
        return self.descriptor.get('drawingInfo').get('labelingInfo')

    @property
    def spatialReference(self):
        return self.descriptor.get('extent').get('spatialReference').get(
            'wkid')

    def urljoin(self, *args):
        return "/".join(map(lambda x: str(x).rstrip('/'), args))

    def _determine_renderer(self, renderer_type):
        return self._renderers.get(renderer_type, self._render_default)

    def _determine_type_converter(self, symbol_type):
        return self._type_converters.get(symbol_type,
                                         self._convert_esriTypeDefault)

    def _determine_style_converter(self, symbol_style):
        return self._style_converters.get(symbol_style,
                                          self._convert_esriStyleDefault)

    def _parse_drawingInfo(self):
        namedLayer = self.sld_doc.create_namedlayer(self.name)
        userStyle = namedLayer.create_userstyle()
        featureTypeStyle = userStyle.create_featuretypestyle()

        renderer_type = self.renderer.get('type')

        renderer = self._determine_renderer(renderer_type)
        renderer(featureTypeStyle)

        self._parse_labelingInfo(featureTypeStyle)

    def _parse_labelingInfo(self, featureTypeStyle):
        if not self.labelingInfo: return

        for labelRule in self.labelingInfo:
            labelPlacement = labelRule.get('labelPlacement')
            labelExpression = slugify(
                labelRule.get('labelExpression').replace('[', '').replace(
                    ']', ''))
            symbol = labelRule.get('symbol')
            symbolType = symbol.get('type')

            rule = featureTypeStyle.create_rule("Labels")
            del rule.PointSymbolizer

            converter = self._determine_type_converter(symbolType)
            converter(rule, labelExpression, labelPlacement, symbol)

    def _render_esriSimple(self, featureTypeStyle):
        scales = self._convert_esriScales()

        rule = featureTypeStyle.create_rule(
            self.name,
            MinScaleDenominator=scales.get('max_scale'),
            MaxScaleDenominator=scales.get('min_scale'))
        del rule.PointSymbolizer

        symbol = self.renderer.get('symbol')
        symbol_type = symbol.get('type')

        type_converter = self._determine_type_converter(symbol_type)
        type_converter(rule, symbol)

    def _render_uniqueValue(self, featureTypeStyle):
        field1 = self.renderer.get('field1')
        uniqueValueInfos = self.renderer.get('uniqueValueInfos')
        scales = self._convert_esriScales()

        for uniqueValue in uniqueValueInfos:
            rule_label = uniqueValue.get('label')
            rule_value = uniqueValue.get('value')

            rule = featureTypeStyle.create_rule(
                rule_label,
                MinScaleDenominator=scales.get('max_scale'),
                MaxScaleDenominator=scales.get('min_scale'))
            del rule.PointSymbolizer

            rule.create_filter(field1, '==', rule_value)

            symbol = uniqueValue.get('symbol')
            symbol_type = symbol.get('type')

            type_converter = self._determine_type_converter(symbol_type)
            type_converter(rule, symbol)

    def _render_classBreaks(self, featureTypeStyle):
        field = self.renderer.get('field')
        minValue = str(self.renderer.get('minValue'))
        classBreakInfos = self.renderer.get('classBreakInfos')
        scales = self._convert_esriScales()

        for classBreakInfo in classBreakInfos:
            rule_label = classBreakInfo.get('label')
            classMaxValue = str(classBreakInfo.get('classMaxValue'))

            rule = featureTypeStyle.create_rule(
                rule_label,
                MinScaleDenominator=scales.get('max_scale'),
                MaxScaleDenominator=scales.get('min_scale'))
            del rule.PointSymbolizer

            filter1 = sld.Filter(rule)
            filter1.PropertyIsGreaterThanOrEqualTo = sld.PropertyCriterion(
                filter1, 'PropertyIsGreaterThanOrEqualTo')
            filter1.PropertyIsGreaterThanOrEqualTo.PropertyName = field
            filter1.PropertyIsGreaterThanOrEqualTo.Literal = minValue

            filter2 = sld.Filter(rule)
            filter2.PropertyIsLessThanOrEqualTo = sld.PropertyCriterion(
                filter2, 'PropertyIsLessThanOrEqualTo')
            filter2.PropertyIsLessThanOrEqualTo.PropertyName = field
            filter2.PropertyIsLessThanOrEqualTo.Literal = classMaxValue

            rule.Filter = filter1 + filter2
            minValue = classMaxValue

            symbol = classBreakInfo.get('symbol')
            symbol_type = symbol.get('type')

            converter = self._determine_type_converter(symbol_type)
            converter(rule, symbol)

    def _render_default(self, featureTypeStyle):
        scales = self._convert_esriScales()

        if self.geometryType == "esriGeometryPoint":
            rule = featureTypeStyle.create_rule(
                self.name,
                symbolizer=sld.PointSymbolizer,
                MinScaleDenominator=scales.get('max_scale'),
                MaxScaleDenominator=scales.get('min_scale'))

        elif self.geometryType == "esriGeometryPolyline":
            rule = featureTypeStyle.create_rule(
                self.name,
                symbolizer=sld.LineSymbolizer,
                MinScaleDenominator=scales.get('max_scale'),
                MaxScaleDenominator=scales.get('min_scale'))

        elif self.geometryType == "esriGeometryPolygon":
            rule = featureTypeStyle.create_rule(
                self.name,
                symbolizer=sld.PolygonSymbolizer,
                MinScaleDenominator=scales.get('max_scale'),
                MaxScaleDenominator=scales.get('min_scale'))

    def _convert_esriScales(self):
        min_scale = self.descriptor.get('minScale')
        max_scale = self.descriptor.get('maxScale')

        if min_scale == 0:
            min_scale = None
        else:
            min_scale = str(min_scale)

        if max_scale == 0:
            max_scale = None
        else:
            max_scale = str(max_scale)

        return {'min_scale': min_scale, 'max_scale': max_scale}

    def _convert_esriPMS(self, rule, symbol, img_type='svg'):
        symbolizer = rule.create_symbolizer('Point')
        graphic = symbolizer.create_element("sld", 'Graphic')
        externalGraphic = graphic.create_element("sld", "ExternalGraphic")

        symbol_size = str(symbol.get('width'))
        symbol_contentType = symbol.get('contentType')
        base64data = symbol.get('imageData')

        sld_icon_format = None
        icon_ext = None
        icon_name = slugify(rule.Title).replace("-", "_")
        if img_type == 'img':
            icon_ext = symbol_contentType.split('/')[1]
            sld_icon_format = "image/{}".format(icon_ext)
        else:
            icon_ext = "svg"
            sld_icon_format = "image/svg+xml"
            graphic.Size = symbol_size

        icon_file_name = os.path.join(self.name, "{}.{}".format(
            icon_name, icon_ext))
        icon_file_path = os.path.join(self.dump_folder, icon_file_name)
        self.dump_icon_file(icon_file_path, base64data)

        externalGraphic.create_online_resource(icon_file_name)
        externalGraphic.Format = sld_icon_format

    def _convert_esriSFS(self, rule, symbol):
        symbolizer = rule.create_symbolizer('Polygon')

        fill_color = symbol.get('color')
        if fill_color:
            fill = symbolizer.create_fill()
            fill_opacity = str(fill_color[3] / 255)
            fill.create_cssparameter('fill', self._convert_color(fill_color))
            fill.create_cssparameter('fill-opacity', fill_opacity)

        stroke_color = symbol.get('outline').get('color')
        if stroke_color:
            stroke = symbolizer.create_stroke()
            stroke_width = str(symbol.get('outline').get('width'))

            stroke.create_cssparameter('stroke',
                                       self._convert_color(stroke_color))
            stroke.create_cssparameter('stroke-width', stroke_width)
            stroke.create_cssparameter('stroke-linejoin', 'bevel')
            stroke.create_cssparameter('stroke-opacity',
                                       str(stroke_color[3] / 255))

        symbol_style = symbol.get('style')
        style_converter = self._determine_style_converter(symbol_style)
        style_converter(symbolizer, symbol)

    def _convert_esriSLS(self, rule, symbol):
        if not symbol.get('outline'):
            stroke_color = symbol.get('color')
            stroke_width = str(symbol.get('width'))
            stroke_style = symbol.get('style')
        else:
            outline = symbol.get('outline')
            stroke_color = outline.get('color')
            stroke_width = str(outline.get('width'))
            stroke_style = outline.get('style')

        symbolizer = rule.create_symbolizer('Line')
        stroke = symbolizer.create_stroke()

        stroke.create_cssparameter('stroke', self._convert_color(stroke_color))
        stroke.create_cssparameter('stroke-width', stroke_width)
        stroke.create_cssparameter('stroke-linejoin', 'bevel')

        style_converter = self._determine_style_converter(stroke_style)
        style_converter(symbolizer, symbol)

    def _convert_esriSMS(self, rule, symbol):
        symbolizer = rule.create_symbolizer('Point')

        symbol_style = symbol.get('style')
        style_converter = self._determine_style_converter(symbol_style)
        style_converter(symbolizer, symbol)

    def _convert_esriTS(self, rule, labelExpression, labelPlacement, symbol):
        symbolizer = rule.create_symbolizer('Text')

        label = symbolizer.create_label()
        label.PropertyName = labelExpression

        fill = symbolizer.create_fill()

        fill_color = symbol.get('color')
        fill_opacity = str(fill_color[3] / 255)

        fill.create_cssparameter('fill', self._convert_color(fill_color))
        fill.create_cssparameter('fill-opacity', fill_opacity)

        agsfont = symbol.get('font')
        font_family = agsfont.get('family')
        font_size = str(agsfont.get('size'))
        font_style = agsfont.get('style')
        font_weight = agsfont.get('weight')
        font_decoration = agsfont.get('decoration')

        font = symbolizer.create_font()
        font.create_cssparameter('font-family', font_family)
        font.create_cssparameter('font-size', font_size)
        font.create_cssparameter('font-style', font_style)
        font.create_cssparameter('font-weight', font_weight)

        if symbol.get('haloSize'):
            halo = symbolizer.create_halo()
            halo_size = str(symbol.get('haloSize'))
            halo.Radius = halo_size

            halo_fill = halo.create_fill()
            halo_fill_color = symbol.get('haloColor')
            halo_fill_opacity = str(halo_fill_color[3] / 255)
            halo_fill.create_cssparameter('fill',
                                          self._convert_color(halo_fill_color))

        verticalAlignment = symbol.get('verticalAlignment')
        horizontalAlignment = symbol.get('horizontalAlignment')

        label_placement = symbolizer.create_label_placement()
        point_placement = label_placement.create_point_placement()
        anchor_point = point_placement.create_anchor_point()

        if horizontalAlignment == "left":
            anchor_point.AnchorPointX = "0.0"
        elif horizontalAlignment == "center":
            anchor_point.AnchorPointX = "0.5"
        else:
            anchor_point.AnchorPointX = "1.0"

        if verticalAlignment == "bottom" or verticalAlignment == "baseline":
            anchor_point.AnchorPointY = "0.0"
        elif verticalAlignment == "center":
            anchor_point.AnchorPointY = "0.5"
        else:
            anchor_point.AnchorPointY = "1.0"

    def _convert_esriTypeDefault(self, rule, symbol):
        pass

    def _convert_esriSMSCircle(self, symbolizer, symbol):
        graphic = symbolizer.create_element("sld", 'Graphic')
        graphic.Size = str(symbol.get('size'))

        mark = graphic.create_element("sld", "Mark")
        mark.WellKnownName = "circle"

        fill = mark.create_fill()
        fill_color = symbol.get('color')
        fill_opacity = str(fill_color[3] / 255)

        fill.create_cssparameter('fill', self._convert_color(fill_color))
        fill.create_cssparameter('fill-opacity', fill_opacity)

    def _convert_esriSLSDash(self, symbolizer, symbol):
        symbolizer.Stroke.create_cssparameter('stroke-linecap', 'square')
        symbolizer.Stroke.create_cssparameter('stroke-dasharray', '4 2')

    def _convert_esriSLSDashDotDot(self, symbolizer, symbol):
        pass

    def _convert_esriSFSSolid(self, symbolzer, symbol):
        pass

    def _convert_esriSLSSolid(self, symbolizer, symbol):
        pass

    def _convert_esriStyleDefault(self, symbolizer, symbol):
        graphic = symbolizer.create_element("sld", 'Graphic')
        graphic.Size = str(symbol.get('size'))

        mark = graphic.create_element("sld", "Mark")
        mark.WellKnownName = "dot"

        fill = mark.create_fill()
        fill_color = symbol.get('color')
        fill_opacity = str(fill_color[3] / 255)

        fill.create_cssparameter('fill', self._convert_color(fill_color))
        fill.create_cssparameter('fill-opacity', fill_opacity)

    def _convert_color(self, color):
        r, g, b, a = color
        color_hex = '#{:02x}{:02x}{:02x}'.format(r, g, b)
        return color_hex

    def dump_icon_file(self, icon_file, base64data):
        if not os.path.exists(os.path.dirname(icon_file)):
            try:
                os.makedirs(os.path.dirname(icon_file))
            except OSError as exc:  # Guard against race condition
                if exc.errno != errno.EEXIST:
                    raise
        filename, ext = os.path.splitext(icon_file)
        if ext == ".svg":
            startSvgTag = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
            <!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN"
            "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
            <svg version="1.1"
            xmlns="http://www.w3.org/2000/svg"
            xmlns:xlink="http://www.w3.org/1999/xlink"
            width="240px" height="240px" viewBox="0 0 240 240">"""

            endSvgTag = """</svg>"""
            base64String = '<image xlink:href="data:image/png;base64,{0}" width="240" height="240" x="0" y="0" />'.format(
                base64data.decode('utf-8'))
            data = startSvgTag + base64String + endSvgTag
        else:
            data = base64.b64decode(base64data.encode())
        with open(icon_file, "wb") as fh:
            fh.write(data)

        print("  {}".format(os.path.basename(icon_file)))

    def dump_sld_file(self):

        self.parse()

        sld_name = self.name
        sld_file = "{}.{}".format(sld_name, "sld")
        sld_file_path = os.path.join(self.dump_folder, sld_file)

        self.sld_doc.normalize()

        with open(sld_file_path, 'w') as the_file:
            the_file.write(
                lxml.etree.tostring(
                    self.sld_doc._node,
                    pretty_print=True,
                    encoding="UTF-8",
                    xml_declaration=True))
        # TODO: use logger instead of print function
        print("  {}".format(os.path.basename(sld_file_path)))

    def parse(self):
        if self.descriptor.get('type') == "Feature Layer":
            self._parse_drawingInfo()
        else:
            # TODO: use logger instead of print function
            print("  {} not parsed...".format(self.descriptor.get('type')))