# Lonely Binary SPI TFT LCD Kit: CAD and Enclosure Reference

Prepared October 1, 2026, for Jason McPheron.

Primary focus: the 2.8-inch panel in the six-display kit, Amazon ASIN B0GR4HRVV2.

## What this reference establishes

This is a working engineering reference, not a manufacturer mechanical drawing. The available information supports an approximate display placeholder and a measurement plan. It does not establish the PCB envelope, mounting-hole coordinates, glass envelope, or installed thickness accurately enough for a final enclosure.

All physical dimensions below are in millimeters unless specified otherwise. A blank or `TBD` means there is no verified value, not zero.

Evidence categories:

| Label | Meaning |
| --- | --- |
| Documented | Confirmed in the manufacturer pages linked below |
| Calculated | Derived from advertised diagonal and pixel aspect ratio, assuming square pixels |
| Earlier finding | Reported in the preceding conversation, but not independently rechecked here |
| User listing | Present in the Amazon listing text supplied by the user |
| Measure | Must be established from the actual hardware or an authoritative mechanical drawing |
| Design suggestion | A proposed modeling or printing choice, not a product specification |

## 1. Most useful measurements for the 2.8-inch screen

| Feature | Value | Evidence and limitation |
| --- | ---: | --- |
| Advertised diagonal | 2.8 in | Documented; nominal size |
| Nominal diagonal converted to mm | 71.12 | Calculated: 2.8 × 25.4 |
| Native image resolution | 240 × 320 pixels | Documented |
| Nominal image aspect ratio | 3:4 | Calculated from resolution |
| Estimated active width, portrait | 42.672 | Calculated; not measured |
| Estimated active height, portrait | 56.896 | Calculated; not measured |
| Estimated active width, landscape | 56.896 | Same estimate rotated |
| Estimated active height, landscape | 42.672 | Same estimate rotated |
| Estimated pixel pitch | 0.1778 | Calculated in either direction |
| Estimated pixel density | 142.86 pixels/in | Calculated |
| Breakout pad spacing | 2.54 | Documented |
| First-to-last center span of eight pads | 17.78 | Calculated: seven intervals × 2.54; does not define hole size or board position |
| FPC contact count | 15 | Documented |
| FPC contact pitch | TBD | Previously stated as 1.0 mm; not confirmed in the pages rechecked |
| PCB width and height | TBD | Measure |
| PCB thickness | TBD | Measure |
| Glass/module width and height | TBD | Measure |
| Actual active image dimensions | TBD | Measure with a lit test pattern |
| Mounting-hole diameter and spacing | TBD | Measure |
| Screen position relative to PCB | TBD | Measure |
| Front and rear protrusions | TBD | Measure |
| Connector body and cable exit envelope | TBD | Measure |

**Use approximately 42.7 × 56.9 mm only for an early active-image placeholder. Do not use these numbers as the board dimensions or glass dimensions.**

### Calculation

For square pixels and a 240:320 image ratio, the sides form a 3:4:5 triangle:

```text
diagonal_mm = 2.8 * 25.4 = 71.12
active_width_estimate = diagonal_mm * 3 / 5 = 42.672
active_height_estimate = diagonal_mm * 4 / 5 = 56.896
pixel_pitch_estimate = 42.672 / 240 = 0.1778
```

The arithmetic is precise, but the starting diagonal is a nominal marketing value. Keep the extra decimal places only for reproducibility, not as a claim of machining accuracy.

## 2. Correction to the earlier bezel-opening suggestion

The earlier response suggested an opening of approximately 41.5 × 55.5 mm. That opening is smaller than the estimated active image. If centered, it would cover approximately 0.586 mm at each left/right edge and 0.698 mm at each top/bottom edge, roughly three to four pixels per edge.

Do not treat that opening as a recommended full-image window. It is usable only if cropping is intentional and the UI keeps content away from the covered edges.

For full image visibility, measure the illuminated area and place the bezel overlap over the inactive border. The glass outline, inactive border, and active image are separate geometries. A protective window may need additional allowance for placement error and off-axis viewing.

## 3. All six screen sizes: calculated image envelopes

The manufacturer handbook gives the sizes, resolutions, and controller families below. The millimeter envelopes are calculations, not mechanical drawings. [Source: manufacturer handbook](https://learn.lonelybinary.com/manuals/spi-tft-kit).

| Nominal diagonal | Resolution | Controller family | Diagonal mm | Estimated portrait image W × H mm | Estimated pixel pitch mm |
| --- | --- | --- | ---: | --- | ---: |
| 0.96 in | 80 × 160 | ST7735 | 24.384 | 10.905 × 21.809 | 0.1363 |
| 1.8 in | 128 × 160 | ST7735 | 45.720 | 28.561 × 35.701 | 0.2231 |
| 2.0 in | 240 × 320 | ST7789 | 50.800 | 30.480 × 40.640 | 0.1270 |
| 2.4 in | 240 × 320 | ST7789 | 60.960 | 36.576 × 48.768 | 0.1524 |
| 2.8 in | 240 × 320 | ST7789 | 71.120 | 42.672 × 56.896 | 0.1778 |
| 3.5 in | 320 × 480 | ST7796 | 88.900 | 49.313 × 73.969 | 0.1541 |

General calculation:

```text
d = advertised_diagonal_inches * 25.4
W = d * horizontal_pixels / sqrt(horizontal_pixels^2 + vertical_pixels^2)
H = d * vertical_pixels / sqrt(horizontal_pixels^2 + vertical_pixels^2)
```

The connector standard supports electrical interchangeability. It does not establish interchangeable mechanical mounting or identical PCB outlines.

## 4. Electrical and software facts relevant to enclosure planning

The manufacturer specifies 3.3 V operation, SPI, RGB565, a 15-contact FPC connection, and eight breakout signals. There is no touch controller or microSD socket. The 2.8-inch backlight is active high and PWM capable. [Source: manufacturer handbook](https://learn.lonelybinary.com/manuals/spi-tft-kit).

| Breakout label | Function |
| --- | --- |
| BL | Backlight control |
| RST | Display reset |
| DC | Data/command selection |
| SCL | SPI clock, despite the I2C-like label |
| MOSI | Data from MCU to display |
| CS | Chip select |
| 3V3 | Power |
| GND | Ground |

This is the breakout pad order, not a verified mapping of FPC contacts 1 through 15. Do not infer a ribbon pinout from the eight labels.

### Findings from the earlier repository inspection

The preceding answer reported these values for `tft_28` in `panels.yaml`:

| Setting | Earlier reported value |
| --- | --- |
| Controller | ST7789 |
| Resolution | 240 × 320 |
| Pixel offsets | Zero |
| SPI clock | 40 MHz |
| Backlight polarity | Active high |

Repository: [LonelyBinaryDisplay](https://github.com/Lonely-Binary/LonelyBinaryDisplay).

Panel table: [panels.yaml](https://github.com/Lonely-Binary/LonelyBinaryDisplay/blob/main/panels.yaml).

The repository could not be retrieved during this follow-up. These values are preserved as earlier findings rather than freshly verified entries. The handbook also notes that the table distinguishes measured and inferred specifications. A configured SPI clock is not proof of a guaranteed maximum clock for every cable arrangement.

### Information from the user-provided listing

The listing names ST7735S, ST7789, and ST7796 controllers, advertises IPS panels, and mentions TFT_eSPI, LovyanGFX, and MicroPython st7789/st7735 support. The handbook uses the broader ST7735 family designation. Exact chip suffixes and panel construction should be checked against the supplied unit if important.

The listing describes six screens, nine cables in three lengths, two straight and two right-angle 40-pin breakaway headers, and a case. Exact cable lengths were not supplied.

## 5. Connector and cable mechanics

The ribbon handbook specifies a ZIF latch and contacts facing the PCB, matching the board's printed orientation label. It recommends the shortest cable that reaches and describes straight versus right-angle headers as alternative mounting arrangements. [Source: ribbon/header handbook](https://learn.lonelybinary.com/manuals/spi-tft-kit/the-ribbon-or-the-header).

For CAD, model three separate regions:

1. The fixed connector body.
2. The space swept by the latch while opening.
3. The installed cable path, including the stiffened end and a gentle bend.

Do not assign a minimum bend radius without the cable specification. Provide room for a smooth bend and avoid a sharp crease. Make the latch reachable if the enclosure must support servicing.

| Connector/cable measurement | Value |
| --- | --- |
| Connector width | TBD |
| Connector depth | TBD |
| Closed connector height above PCB | TBD |
| Open latch maximum height | TBD |
| Connector X/Y position | TBD |
| Cable exit direction | TBD |
| Cable width | TBD |
| Cable thickness | TBD |
| Stiffener length and thickness | TBD |
| Cable pitch | TBD |
| Short, medium, long cable lengths | TBD / TBD / TBD |
| Service access allowance | Design parameter |

If using a header, measure the assembled header, female housing, and wire bend, not just the metal pins. These can determine the required enclosure depth.

## 6. What has not been established

No dimensioned manufacturer mechanical drawing was found in the reviewed material. The following remain unknown:

- PCB outline, corner radii, and thickness.
- Hole diameter, exact hole centers, and whether the pattern is symmetric.
- Glass, metal frame, and inactive border dimensions.
- Screen alignment on the carrier board.
- Front and rear Z envelopes.
- Connector part number, exact pitch, and detailed geometry.
- FPC cable lengths and specified bend radius.
- Board manufacturing and assembly tolerances.
- Recommended mounting screw size or torque.
- Current draw and thermal data for this exact module.

The manufacturer image description identifies four gold-ringed mounting holes. Their dimensions are not supplied. The attached user image was unavailable at its supplied local path during this turn, so no measurements were extracted from it.

Do not substitute measurements from a generic 2.8-inch ST7789 breakout. The same controller and image size can appear on different carrier boards.

## 7. Coordinate system for an Onshape or other CAD reference part

Suggested front-view convention:

- Face the screen in portrait orientation.
- Set X = 0 and Y = 0 at the lower-left corner of the PCB bounding rectangle.
- X increases right; Y increases up.
- Set Z = 0 at the front surface of the PCB.
- Positive Z points toward the viewer; negative Z points behind the board.

Record which edge holds the connector. Photograph the orientation alongside your measurements so front and back views do not get mirrored accidentally.

Use the PCB bounding box as a reference even if its corners are rounded. Define each mounting hole by its individual X/Y center. Apply symmetry only after measuring it.

## 8. Measurement worksheet

### PCB and mounting

| Parameter | Description | Measured mm |
| --- | --- | --- |
| pcb_w | Overall PCB width | |
| pcb_h | Overall PCB height | |
| pcb_t | PCB substrate thickness | |
| pcb_corner_r | Corner radius, if needed | |
| hole_1_d | Lower-left hole diameter | |
| hole_1_x | Lower-left hole center X | |
| hole_1_y | Lower-left hole center Y | |
| hole_2_d | Lower-right hole diameter | |
| hole_2_x | Lower-right hole center X | |
| hole_2_y | Lower-right hole center Y | |
| hole_3_d | Upper-right hole diameter | |
| hole_3_x | Upper-right hole center X | |
| hole_3_y | Upper-right hole center Y | |
| hole_4_d | Upper-left hole diameter | |
| hole_4_x | Upper-left hole center X | |
| hole_4_y | Upper-left hole center Y | |
| mounting_land_d | Usable flat support diameter around holes | |

### Display face

| Parameter | Description | Measured mm |
| --- | --- | --- |
| glass_w | Glass/module outer width | |
| glass_h | Glass/module outer height | |
| glass_x | Left edge position relative to origin | |
| glass_y | Bottom edge position relative to origin | |
| front_z_max | Highest front surface above PCB | |
| active_w | Actual illuminated width | |
| active_h | Actual illuminated height | |
| active_x | Illuminated area's left edge X | |
| active_y | Illuminated area's bottom edge Y | |
| frame_w | Outer metal frame width, if distinct | |
| frame_h | Outer metal frame height, if distinct | |

Turn on a solid-color image or an edge test pattern to distinguish the active pixels from a dark border. Keep caliper jaws away from the glass face and flexible tail.

### Rear clearance

| Parameter | Description | Measured mm |
| --- | --- | --- |
| rear_projection | Maximum projection beyond rear PCB surface | |
| connector_x | Connector body's left edge X | |
| connector_y | Connector body's bottom edge Y | |
| connector_w | Connector body width | |
| connector_h | Connector body height in the PCB plane | |
| connector_z_min | Rearmost connector point using this Z convention | |
| latch_open_envelope | Space needed with latch open | |
| header_envelope | Installed header and mating plug volume | |

With this coordinate system, the rear PCB face lies at `Z = -pcb_t`. If a component projects `rear_projection` beyond that face, its rear extent is `Z = -(pcb_t + rear_projection)`.

### Practical hole measurements

For a round hole, center distance from an edge equals the distance to its nearest tangent plus half the diameter. For two equal holes, center spacing equals the farthest outside span minus one hole diameter, or the nearest inside gap plus one hole diameter. Repeat the measurement and compare both methods.

Do not assume a gold ring's diameter is the drilled hole diameter. Do not assume the holes accept M2 or M3 screws before measuring.

## 9. Parametric model structure

Create a reusable display reference component with separately identifiable parts or sketches:

| Model element | Purpose |
| --- | --- |
| PCB solid | Overall fit and mounting reference |
| Mounting holes | Standoff and fastener placement |
| Glass/frame solid | Front depth and support avoidance |
| Active-area sketch | Bezel window and UI alignment |
| Connector solid | Fixed rear clearance |
| Latch keep-out | Service access |
| Cable keep-out | Routing space |
| Header keep-out | Optional wiring configuration |

Keep estimated image dimensions in parameters named `active_w_est` and `active_h_est`. Keep measured values separately until the model is updated. Unknown dimensions should remain visibly unresolved instead of being silently replaced with common values such as a 1.6 mm PCB thickness.

For Onshape, make the screen its own Part Studio or reference part and bring it into the enclosure workflow. Keep the electrical connector convention separate from the mechanical mounting interface when building variants for other sizes.

## 10. Enclosure design parameters

These are design inputs, not dimensions of the display:

| Parameter | Purpose |
| --- | --- |
| pcb_clearance_xy | Clearance per side around the PCB |
| rear_clearance_z | Space beyond rear components |
| bezel_overlap | Overlap over measured inactive border |
| glass_gap_z | Gap preventing bezel pressure on glass |
| standoff_height | Board mounting position in the case |
| screw_clearance_d | Printed fastener hole size |
| cable_channel_clearance | Allowance around installed ribbon |
| wall_t | Case wall thickness |
| window_t | Optional protective window thickness |

For a first FDM fit coupon, roughly 0.2–0.4 mm clearance per side around a non-interference PCB pocket is a reasonable experimental starting range. This is not a universal tolerance. Tune it for the printer, material, orientation, and actual measurements.

Support the PCB on appropriate mounting lands. Avoid transferring clamping force through the LCD glass. Check screw-head clearance against nearby components and the screen frame. Verify that case closure does not squeeze the ribbon or press the latch.

Print a small mounting and bezel coupon before printing the full case. Include the hole pattern, one or two board corners, and the relevant window edge. This checks the expensive-to-correct fit features with little material.

## 11. Suggested measurement and CAD sequence

1. Record the exact PCB markings and revision.
2. Measure PCB width, height, and thickness.
3. Measure all four hole diameters and center coordinates.
4. Measure the glass/frame envelope and placement.
5. Light the display and establish the true active image boundary.
6. Measure front and rear Z envelopes.
7. Install the intended cable or header and measure its occupied space.
8. Build the reference component and label estimates.
9. Design the bezel against the measured active area and inactive border.
10. Print a fit coupon, then adjust the clearance parameters.
11. Build the full enclosure and check cable access and case closure.

## 12. Source index and further leads

| Source | Link | What it contributes |
| --- | --- | --- |
| User's Amazon product | https://www.amazon.com/dp/B0GR4HRVV2 | Product identification and listing text supplied by the user |
| Manufacturer product page | https://lonelybinary.com/products/6-pack-spi-tft-lcd-display-kit-0-96-3-5 | Matches SKU B0GR4HRVV2; kit and compatibility information |
| Manufacturer handbook | https://learn.lonelybinary.com/manuals/spi-tft-kit | Screen sizes, resolutions, controller families, signals, and links |
| Ribbon/header handbook | https://learn.lonelybinary.com/manuals/spi-tft-kit/the-ribbon-or-the-header | Connector handling and cable routing considerations |
| Display library | https://github.com/Lonely-Binary/LonelyBinaryDisplay | Driver implementation and configuration reference |
| Panel table | https://github.com/Lonely-Binary/LonelyBinaryDisplay/blob/main/panels.yaml | Earlier reported per-panel settings; not retrievable in this follow-up |

The handbook links ST7735R and ST7789V controller datasheets. Controller datasheets explain the silicon and interface; they do not define this particular carrier PCB's mounting geometry.

The product page advertises a browser 3D view, but its link in the retrieved page points back to the handbook. No downloadable STEP model or dimensionally validated carrier-board model was established during this review.

Manufacturer contact listed on its product page: `office@lonelybinary.com`.

If requesting mechanical information, ask specifically for the 2.8-inch board in ASIN/SKU B0GR4HRVV2, including PCB revision, dimensioned outline, hole center coordinates and diameters, active-area and glass placement, Z stack, FPC connector part number/pitch, and STEP or PCB CAD files. A generic ST7789 datasheet will not resolve those questions.

## 13. Current CAD readiness

You can create an approximate active-image placeholder now: **42.7 × 56.9 mm in portrait**. You can also plan an SPI/FPC wiring arrangement.

A dimensionally trustworthy holder still requires the actual PCB outline, hole pattern, screen placement, and component/cable envelope. The measurement worksheet above is the path from the documented electrical product to a reusable CAD component.
