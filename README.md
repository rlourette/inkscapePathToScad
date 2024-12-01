# inkscapePathToScad (AKA Paths2OpenSCAD)  - Inkscape Extension
Inkscape path export to Open Scad

An Inkscape extension to export paths to OpenSCAD polygons. This extension handles SVG arcs, clones, circles, ellipses, groups, lines, paths, polygons, polylines, rects, and splines. It also follows document transforms and viewports.

Originally created by Dan Newman (dnewman) and shared on [Thingiverse](https://www.thingiverse.com/thing:24808). This is Version 4, updated to work with modern versions of Python and Inkscape.

## Features

- Processes entire documents or selected portions
- Handles complex SVG elements including:
  - Arcs
  - Clones
  - Circles/Ellipses
  - Groups
  - Lines
  - Paths
  - Polygons/Polylines
  - Rectangles
  - Splines
- Supports document transforms and viewports
- Handles single level polygon nesting
- Generates clean OpenSCAD module names (alphanumeric only)
- Updated for modern Python 3 and current Inkscape versions
- Improved error handling and file operations

## Installation

1. Download the latest release (paths2openscad-4.zip)
2. Extract the files:
   - paths2openscad.py
   - paths2openscad.inx

3. Place these files in your Inkscape extensions folder:
   - Linux/OS X: `~/.config/inkscape/extensions/`
   - Windows: `C:/Program Files/Inkscape/share/extensions/`

4. Restart Inkscape

The extension will appear under "Extensions > Generate from Path > Paths to OpenSCAD"

## Usage

1. Set your document properties:
   - Set units to millimeters
   - Set reasonable document dimensions (e.g., 100 x 100 mm)
   - Access via "File > Document Properties"

2. Switch to outline display mode:
   - View > Display Mode > Outline

3. Convert objects to paths:
   - Select objects to convert
   - Path > Object to Path
   - Note: Text must be converted to paths

4. Select objects to export:
   - Select specific objects, or
   - Deselect all for entire document

5. Run the extension:
   - Extensions > Generate from Path > Paths to OpenSCAD
   - Enter output filename
   - Set extrusion height
   - Set smoothing parameter (default 0.2)
   - Click "Apply"

## Limitations

- Only handles single level of polygon nesting
- For polygon subtraction, combine polygons into a single path:
  - Select polygons
  - Path > Combine
  - (Not needed for text converted to paths)
- Some complex polygons may render in OpenSCAD with F5 but fail with F6

## Alternative Approach

You can also import SVG into OpenSCAD by:
1. Saving as DXF from Inkscape
2. Using OpenSCAD's `import()` function

## License

GNU GPL License

## Acknowledgments

Much of the core code is derived from work done by Dan Newman and others while developing the Inkscape driver for the Eggbot.

## Version History

- V4: Updated for Python 3 and modern Inkscape, improved error handling
- V3: See [Thing 25036](http://www.thingiverse.com/thing:25036)
- V2: Added single level polygon nesting, fixed Windows file path handling
- V1: Initial release
