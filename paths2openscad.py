#!/usr/bin/env python3
"""
paths2openscad.py - Inkscape Extension for OpenSCAD Export
Version 4.0

An Inkscape extension to export paths to OpenSCAD polygons. This extension handles 
SVG arcs, clones, circles, ellipses, groups, lines, paths, polygons, polylines, 
rects, and splines. It also follows document transforms and viewports.

Features:
- Processes entire documents or selected portions
- Handles complex SVG elements
- Supports document transforms and viewports
- Handles single level polygon nesting
- Generates clean OpenSCAD module names
- Modern Python 3 and current Inkscape compatibility
- Improved error handling and file operations

Originally created by Dan Newman (dan.newman@mtbaldy.us)
Original source: https://www.thingiverse.com/thing:24808
Updated for modern Python and Inkscape compatibility

Installation:
1. Place this file and paths2openscad.inx in your Inkscape extensions folder:
   - Linux/OS X: ~/.config/inkscape/extensions/
   - Windows: C:/Program Files/Inkscape/share/extensions/

Usage:
Access via Extensions > Generate from Path > Paths to OpenSCAD in Inkscape

License: GNU GPL

Version History:
- V4.0: Updated for Python 3 and modern Inkscape, improved error handling
- V3.0: See Thing 25036 (http://www.thingiverse.com/thing:25036)
- V2.0: Added single level polygon nesting, fixed Windows file path handling
- V1.0: Initial release
"""

import math
import os.path
import inkex
from inkex import paths
from inkex import transforms
from inkex import bezier
from inkex import Style
import re
from typing import List, Tuple, Optional, Dict, Any

class OpenSCAD(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--tab", default="splash",
            help="The active tab when Apply was pressed")
        pars.add_argument("--smoothness", type=float, default=0.2,
            help="Curve smoothing (less for more)")
        pars.add_argument("--height", default="5",
            help="Height (mm)")
        pars.add_argument("--fname", default="~/inkscape.scad",
            help="Output filename")

    def __init__(self):
        super().__init__()
        self.cx = float(100) / 2.0  # Default width
        self.cy = float(100) / 2.0  # Default height
        self.xmin, self.xmax = (1.0E70, -1.0E70)
        self.ymin, self.ymax = (1.0E70, -1.0E70)
        self.paths: Dict[Any, List] = {}
        self.call_list: List[str] = []
        self.pathid = 0
        self.f = None
        self.doc_width = float(100)  # Default width
        self.doc_height = float(100)  # Default height
        self.doc_transform = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
        self.warnings: Dict[str, int] = {}

    def get_length_in_pixels(self, value: str, default: float) -> Optional[float]:
        """Convert SVG length to pixels."""
        if not value:
            return float(default)
        
        try:
            return self.svg.unittouu(value)
        except (ValueError, AttributeError):
            return None

    def get_doc_props(self) -> bool:
        """Get document properties."""
        svg = self.document.getroot()
        self.doc_height = self.get_length_in_pixels(svg.get('height'), 100)
        self.doc_width = self.get_length_in_pixels(svg.get('width'), 100)
        return self.doc_height is not None and self.doc_width is not None

    def handle_viewbox(self):
        """Handle SVG viewBox attribute."""
        if self.get_doc_props():
            viewbox = self.svg.get('viewBox')
            if viewbox:
                vinfo = viewbox.strip().replace(',', ' ').split()
                if len(vinfo) == 4 and float(vinfo[2]) != 0 and float(vinfo[3]) != 0:
                    sx = self.doc_width / float(vinfo[2])
                    sy = self.doc_height / float(vinfo[3])
                    self.doc_transform = transforms.Transform(f'scale({sx},{sy})')

    def point_in_bbox(self, pt: List[float], bbox: List[float]) -> bool:
        """Check if point lies within bounding box."""
        return not (pt[0] < bbox[0] or pt[0] > bbox[1] or 
                   pt[1] < bbox[2] or pt[1] > bbox[3])

    def bbox_in_bbox(self, bbox1: List[float], bbox2: List[float]) -> bool:
        """Check if bbox1 lies within bbox2."""
        return not (bbox1[0] < bbox2[0] or bbox1[1] > bbox2[1] or 
                   bbox1[2] < bbox2[2] or bbox1[3] > bbox2[3])

    def point_in_poly(self, p: List[float], poly: List[List[float]], 
                     bbox: Optional[List[float]] = None) -> bool:
        """Ray casting algorithm to check if point lies within polygon."""
        if p is None or poly is None:
            return False

        if bbox is not None and not self.point_in_bbox(p, bbox):
            return False

        if p in poly:
            return True

        x, y = p[0], p[1]
        inside = False
        j = len(poly) - 1

        for i in range(len(poly)):
            if ((poly[i][1] > y) != (poly[j][1] > y) and
                x < (poly[j][0] - poly[i][0]) * (y - poly[i][1]) /
                    (poly[j][1] - poly[i][1]) + poly[i][0]):
                inside = not inside
            j = i

        return inside

    def poly_in_poly(self, poly1: List[List[float]], bbox1: List[float],
                     poly2: List[List[float]], bbox2: List[float]) -> bool:
        """Check if poly2 contains poly1."""
        if bbox1 is not None and bbox2 is not None:
            if not self.bbox_in_bbox(bbox1, bbox2):
                return False

        return all(self.point_in_poly(p, poly2, bbox2) for p in poly1)

    def subdivide_cubic_path(self, sp, flat):
        """
        Break up a bezier curve into smaller curves, each approximately a straight line.
        """
        while True:
            i = 1
            while i < len(sp):
                p0 = sp[i - 1][1]
                p1 = sp[i - 1][2]
                p2 = sp[i][0]
                p3 = sp[i][1]
                
                b = (p0, p1, p2, p3)
                
                # Check if curve needs subdivision
                if bezier.maxdist(b) > flat:
                    one, two = bezier.beziersplitatt(b, 0.5)
                    sp[i - 1][2] = one[1]
                    sp[i][0] = two[2]
                    p = [one[2], one[3], two[1]]
                    sp.insert(i, p)
                else:
                    i += 1
            
            # Check if any segments need subdivision
            needs_subdivision = False
            for i in range(1, len(sp)):
                p0 = sp[i - 1][1]
                p1 = sp[i - 1][2]
                p2 = sp[i][0]
                p3 = sp[i][1]
                if bezier.maxdist((p0, p1, p2, p3)) > flat:
                    needs_subdivision = True
                    break
            
            if not needs_subdivision:
                break

    def get_path_vertices(self, path_d: str, node=None, transform=None):
        """Convert SVG path to list of vertices."""
        if not path_d:
            return None

        try:
            path = paths.CubicSuperPath(paths.Path(path_d))
        except Exception:
            return None

        if transform:
            path = path.transform(transform)

        subpath_list = []
        
        for sp in path:
            if not sp:
                continue
                
            vertices = []
            self.subdivide_cubic_path(sp, self.options.smoothness)

            first_point = sp[0][1]
            if not first_point:
                continue
                
            vertices.append(first_point)
            sp_xmin = sp_xmax = first_point[0]
            sp_ymin = sp_ymax = first_point[1]

            # Skip last point if it's identical to first point
            n = len(sp)
            last_point = sp[n-1][1]
            if (first_point[0] == last_point[0]) and (first_point[1] == last_point[1]):
                n -= 1

            for i in range(1, n):
                pt = sp[i][1]
                if not pt:
                    continue
                    
                vertices.append(pt)
                
                sp_xmin = min(sp_xmin, pt[0])
                sp_xmax = max(sp_xmax, pt[0])
                sp_ymin = min(sp_ymin, pt[1])
                sp_ymax = max(sp_ymax, pt[1])

            if len(vertices) < 3:  # Need at least 3 points for a polygon
                continue

            self.xmin = min(self.xmin, sp_xmin)
            self.xmax = max(self.xmax, sp_xmax)
            self.ymin = min(self.ymin, sp_ymin)
            self.ymax = max(self.ymax, sp_ymax)

            subpath_list.append([vertices, [sp_xmin, sp_xmax, sp_ymin, sp_ymax]])

        if subpath_list:
            self.paths[node] = subpath_list


    def convert_path(self, node):
        """Convert path to OpenSCAD module."""
        path = self.paths[node]
        if not path:
            return

        # Analysis of polygon containment
        contains = [[] for _ in range(len(path))]
        contained_by = [[] for _ in range(len(path))]

        for i in range(len(path)):
            for j in range(i + 1, len(path)):
                if self.poly_in_poly(path[j][0], path[j][1], path[i][0], path[i][1]):
                    contains[i].append(j)
                    contained_by[j].append(i)
                elif self.poly_in_poly(path[i][0], path[i][1], path[j][0], path[j][1]):
                    contains[j].append(i)
                    contained_by[i].append(j)

        # Generate OpenSCAD module
        node_id = node.get('id', '')
        if not node_id:
            node_id = f"{self.pathid}x"
            self.pathid += 1
        else:
            node_id = re.sub('[^A-Za-z0-9_]+', '', node_id)

        self.f.write(f'module poly_{node_id}(h)\n{{\n')
        self.f.write('  scale([25.4/90, -25.4/90, 1]) union()\n  {\n')
        self.call_list.append(f'poly_{node_id}({self.options.height});\n')

        for i, (subpath, bbox) in enumerate(path):
            if contained_by[i]:
                continue

            if not contains[i]:
                # Simple polygon
                self.write_polygon(subpath)
            else:
                # Polygon with holes
                self.write_difference_polygon(subpath, path, contains[i])

        self.f.write('  }\n}\n')

    def write_polygon(self, vertices):
        """Write simple polygon to OpenSCAD file."""
        self.f.write('    linear_extrude(height=h)\n      polygon([')
        points = [f'[{p[0]-self.cx},{p[1]-self.cy}]' for p in vertices]
        self.f.write(','.join(points))
        self.f.write(']);\n')

    def write_difference_polygon(self, vertices, path, holes):
        """Write polygon with holes to OpenSCAD file."""
        self.f.write('    difference()\n    {\n')
        self.f.write('      linear_extrude(height=h)\n        polygon([')
        points = [f'[{p[0]-self.cx},{p[1]-self.cy}]' for p in vertices]
        self.f.write(','.join(points))
        self.f.write(']);\n')

        for hole_idx in holes:
            self.f.write('      translate([0, 0, -fudge])\n')
            self.f.write('        linear_extrude(height=h+2*fudge)\n')
            self.f.write('          polygon([')
            hole_points = [f'[{p[0]-self.cx},{p[1]-self.cy}]' 
                         for p in path[hole_idx][0]]
            self.f.write(','.join(hole_points))
            self.f.write(']);\n')

        self.f.write('    }\n')

    def effect(self):
        """Main effect handler."""
        self.handle_viewbox()

        if self.options.ids:
            # Process selected objects
            for elem_id in self.options.ids:
                elem = self.svg.getElementById(elem_id)
                if elem is not None:
                    transform = transforms.Transform()
                    parent = elem.getparent()
                    while parent is not None:
                        if parent.get('transform'):
                            transform = transforms.Transform(parent.get('transform')) @ transform
                        parent = parent.getparent()
                    self.process_element(elem, transform)
        else:
            # Process entire document
            self.process_element(self.document.getroot(), transforms.Transform())

        # Calculate center of drawing
        self.cx = self.xmin + (self.xmax - self.xmin) / 2.0
        self.cy = self.ymin + (self.ymax - self.ymin) / 2.0

        # Write OpenSCAD file
        try:
            # Clean up the filepath
            filepath = self.options.fname
            filepath = filepath.strip('"\'')  # Remove any quotes
            filepath = os.path.expanduser(filepath)  # Expand user directory (~)
            filepath = os.path.abspath(filepath)  # Convert to absolute path
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8') as self.f:
                self.write_openscad_header()
                
                # Only write paths if we have any
                if self.paths:
                    for key in self.paths:
                        self.f.write('\n')
                        self.convert_path(key)
                    self.f.write('\n')
                    for call in self.call_list:
                        self.f.write(call)
                else:
                    # Write a comment if no paths were found
                    self.f.write('\n// No valid paths found in the SVG file\n')
                    
        except Exception as e:
            self.msg(f'Unable to open or write to the file {filepath}: {str(e)}')
            raise
    def process_element(self, element, transform):
        """Process an SVG element."""
        if element.tag == inkex.addNS('path', 'svg'):
            self.get_path_vertices(element.get('d'), element, transform)
        elif element.tag in {inkex.addNS('rect', 'svg'), 'rect'}:
            self.process_rect(element, transform)
        elif element.tag in {inkex.addNS('line', 'svg'), 'line'}:
            self.process_line(element, transform)
        elif element.tag in {inkex.addNS('polyline', 'svg'), 'polyline',
                           inkex.addNS('polygon', 'svg'), 'polygon'}:
            self.process_poly(element, transform)
        elif element.tag in {inkex.addNS('ellipse', 'svg'), 'ellipse',
                           inkex.addNS('circle', 'svg'), 'circle'}:
            self.process_ellipse(element, transform)
        else:
            for child in element:
                self.process_element(child, transform)

    def write_openscad_header(self):
        """Write OpenSCAD file header."""
        header = '''// Module names are of the form poly_<inkscape-path-id>().
// You can associate a polygon in this OpenSCAD program with the corresponding
// SVG element in the Inkscape document by looking for the XML element with
// the attribute id="inkscape-path-id".

// fudge value ensures that subtracted solids are slightly taller
// in the z dimension than the polygon being subtracted from.
fudge = 0.1;
'''
        self.f.write(header)

    def process_rect(self, node, transform):
        """Process rectangle element."""
        x = float(node.get('x', 0))
        y = float(node.get('y', 0))
        w = float(node.get('width', 0))
        h = float(node.get('height', 0))
        
        d = f'M {x},{y} l {w},0 l 0,{h} l {-w},0 Z'
        self.get_path_vertices(d, node, transform)

    def process_line(self, node, transform):
        """Process line element."""
        x1 = float(node.get('x1', 0))
        y1 = float(node.get('y1', 0))
        x2 = float(node.get('x2', 0))
        y2 = float(node.get('y2', 0))
        
        d = f'M {x1},{y1} L {x2},{y2}'
        self.get_path_vertices(d, node, transform)

    def process_poly(self, node, transform):
        """Process polygon/polyline element."""
        points = node.get('points', '').strip()
        if not points:
            return

        coords = points.split()
        if node.tag.endswith('polygon'):
            d = 'M ' + ' L '.join(coords) + ' Z'
        else:
            d = 'M ' + ' L '.join(coords)
        self.get_path_vertices(d, node, transform)

    def process_ellipse(self, node, transform):
        """Process ellipse/circle element."""
        if node.tag.endswith('ellipse'):
            rx = float(node.get('rx', 0))
            ry = float(node.get('ry', 0))
        else:  # circle
            rx = ry = float(node.get('r', 0))
        
        if rx == 0 or ry == 0:
            return

        cx = float(node.get('cx', 0))
        cy = float(node.get('cy', 0))
        
        # Convert to path: Two arcs making a complete ellipse
        x1 = cx - rx
        x2 = cx + rx
        d = (f'M {x1},{cy} '
             f'A {rx},{ry} 0 1 0 {x2},{cy} '
             f'A {rx},{ry} 0 1 0 {x1},{cy}')
        self.get_path_vertices(d, node, transform)

if __name__ == '__main__':
    OpenSCAD().run()