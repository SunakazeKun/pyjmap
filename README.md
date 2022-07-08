
# pyjmap
**pyjmap** is a high-level implementation of Nintendo's homemade BCSV/JMap data format. This includes methods to construct, analyze, manipulate, deserialize and serialize proper JMap data. Conversion between CSV and BCSV files is also supported. The reverse-engineered specifications of the file format can be accessed on the [Luma's Workshop wiki](https://luma.aurumsmods.com/wiki/BCSV_(File_format)). This flatbuffer-like data type was used in first-party GameCube and Wii games. As the field/column names are hashed, a lookup table needs to be used to retrieve proper field names. For this, the library provides hashtable implementations for *Super Mario Galaxy*, *Super Mario Galaxy 2*, *Luigi's Mansion* and *Donkey Kong Jungle Beat*.

## Setup
This library requires **Python 3.6 or newer**. You can use pip to install *pyjmap*:
```sh
pip install pyjmap
```

## Command usage
Command line operations to convert between JMap and CSV files are supported. The CSV files are required to be in a special format that has been found in some leftover source files from *Super Mario Galaxy 2*. That format is described down below.

You can dump the contents of a BCSV/JMap file to a CSV file using:
```sh
pyjmap tocsv [-le] [-jmapenc JMAP_ENCODING] [-csvenc CSV_ENCODING] {smg,dkjb,lm} JMAP_FILE_PATH CSV_FILE_PATH
```

Proper CSV files can be converted back to BCSV/JMap files using:
```sh
pyjmap tojmap [-le] [-jmapenc JMAP_ENCODING] [-csvenc CSV_ENCODING] {smg,dkjb,lm} CSV_FILE_PATH JMAP_FILE_PATH
```

If ``le`` is set, the data is expected to be stored using little-endian byte order. ``jmapenc`` specifies the encoding of strings in the JMap data and it defaults to ``shift_jisx0213``. ``csvenc`` is the encoding of the CSV file and it uses ``utf-8`` by default. The hash lookup table is specified by ``HASHTABLE``. Supported values are ``smg`` for *Super Mario Galaxy*, ``lm`` for *Luigi's Mansion*, ``sms`` for *Super Mario Sunshine* and ``dkjb`` for *Donkey Kong Jungle Beat*.

## Library usage
The library provides various high-level operations to deal with JMap data. Below is some example code showing the fundamentals of *pyjmap*. Look at [jmap.py](pyjmap/jmap.py) for more information about the different methods.

```python
import pyjmap

# A hash lookup table is required to retrieve the proper names for hashed fields:
hashtbl_smg = pyjmap.SuperMarioGalaxyHashTable()    # Lookup table for Super Mario Galaxy 1/2
hashtbl_sms = pyjmap.SuperMarioSunshineHashTable()  # Lookup table for Super Mario Sunshine
hashtbl_lm = pyjmap.LuigisMansionHashTable()        # Lookup table for Luigi's Mansion
hashtbl_dkjb = pyjmap.JungleBeatHashTable()         # Lookup table for Donkey Kong Jungle Beat

# Create JMapInfo data from files and print number of entries
info = pyjmap.from_file(hashtbl_smg, "GalaxySortIndexTable.bcsv", big_endian=True)  # Big-endian is True by default
info_from_csv = pyjmap.from_csv(hashtbl_smg, "GalaxySortIndexTable.csv")            # Load data from CSV file
print("Number of entries: %d" % len(info))                                          # >> Number of entries: 55

# Print fields
for field in info.fields:
    print(field)  # >> name
                  # >> MapPaneName
                  # >> OpenCondition0
                  # >> OpenCondition1
                  # >> OpenCondition2
                  # >> PowerStarNum
                  # >> GrandGalaxyNo

# Checking if a field exists
print("MapPaneName" in info)  # >> True
print("StageName" in info)    # >> False

# Getting information about a field
field = info.get_field("MapPaneName")  # Get field by name
field = info.get_field(0x7991F36F)     # Get field by hash

print("[%08X]" % field.hash)  # >> [7991F36F]
print(field.name)             # >> MapPaneName
print(field.type)             # >> JMapFieldType.STRING_OFFSET
print("0x%08X" % field.mask)  # >> 0xFFFFFFFF
print(field.shift)            # >> 0

# Manually-specified offsets and bit-packed data
collision_pa = pyjmap.JMapInfo(hashtbl_smg)
collision_pa.manual_offsets = True
collision_pa.create_field("camera_id", pyjmap.JMapFieldType.LONG, 0, mask=0x000000FF, shift_amount=0, offset=0)
collision_pa.create_field("Sound_code", pyjmap.JMapFieldType.LONG, 0, mask=0x00007F00, shift_amount=8, offset=0)
collision_pa.create_field("Floor_code", pyjmap.JMapFieldType.LONG, 0, mask=0x001F8000, shift_amount=15, offset=0)
collision_pa.create_field("Wall_code", pyjmap.JMapFieldType.LONG, 0, mask=0x01E00000, shift_amount=21, offset=0)
collision_pa.create_field("Camera_through", pyjmap.JMapFieldType.LONG, 0, mask=0x02000000, shift_amount=25, offset=0)

# Creating an exact copy of the data
copied = info.copy()

# The following creates a new field called CometMedalNum which uses the LONG data type. The field's default value
# that is applied to all fields is -1. The optional bitmask and shift amount are 0xFFFFFFFF and 0, respectively.
copied.create_field("CometMedalNum", pyjmap.JMapFieldType.LONG, -1, mask=0xFFFFFFFF, shift_amount=0)

# This removes the field OpenCondition2 and its data in all entries.
copied.drop_field("OpenCondition2")

# Accessing entries directly
first = copied[0] # Get first entry from copied data
last = copied[-1] # Get last entry from copied data

# Adding and deleting entries
new_entry = copied.create_entry()  # Creates a new entry with default data for all fields
del copied[-3:]                    # Delete the last three entries from the copied data

# Iterate over all entries and set GrandGalaxyNo to 0
for entry in copied:
    entry["GrandGalaxyNo"] = 0

# Sort entries by name in lexicographic descending order
info.sort_entries(lambda e: e["name"].lower(), reverse=True)

# Get all entries whose name start with "Koopa"
for entry in filter(lambda e: e["name"].startswith("Koopa"), info):
    print(entry)  # >> {'name': 'KoopaJrShipLv1Galaxy', ... }
                  # >> {'name': 'KoopaBattleVs3Galaxy', ... }
                  # >> {'name': 'KoopaBattleVs2Galaxy', ... }
                  # >> {'name': 'KoopaBattleVs1Galaxy', ... }

# Write data to files
pyjmap.write_file(info, "GalaxySortIndexTable_edited.bcsv", big_endian=True)  # Pack and write binary
pyjmap.dump_csv(copied, "GalaxySortIndexTable_copied.csv", encoding="utf-8")  # Dump CSV content

# Pack as little-endian buffer
packed_copied = pyjmap.pack_buffer(copied, big_endian=False)
```

# Data types
The following field data types are supported:

| Identifier | CSV type | Description |
| - | - | - |
| ``JMapFieldType.LONG`` | ``Int`` | 32-bit integer
| ``JMapFieldType.LONG_2`` | ``Int2`` | 32-bit integer
| ``JMapFieldType.SHORT`` | ``Short`` | 16-bit integer
| ``JMapFieldType.CHAR`` | ``Char`` | 8-bit integer
| ``JMapFieldType.FLOAT`` | ``Float`` | single-precission float
| ``JMapFieldType.STRING`` | ``EmbeddedString`` | embedded SJIS string (occupies 31 bytes at max)
| ``JMapFieldType.STRING_OFFSET`` | ``String`` | SJIS string (**not supported in Luigi's Mansion**)

# CSV format
The CSV format is based on the format of known source files that were left in the files of *Super Mario Galaxy 2*:
* All CSV files are comma-delimited and use quote-marks for quoted cell strings. Quoting is only used when necessary.
* The first CSV-row contains the field descriptors. A field descriptor always consists of three components that are separated by double-colons: the field's name, the data type and the default value. All existing CSV types are described in the previous section and are case sensitive!
* The default value for strings is 0 and is always ignored. It is only kept for syntax.
* If an entry's field data is empty, the default value will be used.
* The field name may be a hash if it's a hex-string encapsulated between two square brackets (for example ``[DEADBEEF]``)

Here is an example of a properly-formated CSV file:
```csv
name:String:0,MapPaneName:String:0,OpenCondition0:String:0,OpenCondition1:String:0,OpenCondition2:String:0,PowerStarNum:Char:0,GrandGalaxyNo:Char:0
AstroGalaxy,dummy,,,,0,0
AstroDome,dummy,,,,0,0
LibraryRoom,dummy,,,,0,0
PeachCastleGardenGalaxy,dummy,,,,0,0
EpilogueDemoStage,dummy,,,,0,0
```