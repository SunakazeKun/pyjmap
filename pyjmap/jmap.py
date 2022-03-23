"""
High-level implementation of Nintendo's homemade BCSV / JMap container format that provides methods to construct,
analyze, serialize, deserialize and manipulate JMapInfo data. As the name BCSV suggests, the data is laid out in a
table-like structure. Each column (JMapField) has a name and binary storage information that describes how individual
entries (JMapEntry) are to be interpreted. All integral data types are interpreted as signed data due to the lack of
information about a field's signedness. The reverse-engineered specifications of this format can be accessed on the
Luma's Workshop wiki: https://luma.aurumsmods.com/wiki/BCSV_(File_format)


Different games use different hash algorithms, string encodings and endianness:

Game                            Hash Algorithm  Endianness  Encoding
--------------------------------------------------------------------------
Luigi's Mansion (GameCube)      Old             big         shift_jisx0213
Luigi's Mansion (3DS)           Old             little      utf-8(?)
Super Mario Sunshine            Old             big         shift_jisx0213
Donkey Kong Jungle Beat         New (JGadget)   big         shift_jisx0213
Super Mario Galaxy (Wii)        New (JGadget)   big         shift_jisx0213
Super Mario Galaxy (Switch)     New (JGadget)   little      utf-8
Super Mario Galaxy 2            New (JGadget)   big         shift_jisx0213
"""

__all__ = [
    "JMapException", "calc_old_hash", "calc_jgadget_hash", "JMapHashTable", "SuperMarioGalaxyHashTable",
    "JungleBeatHashTable", "SuperMarioSunshineHashTable", "LuigisMansionHashTable", "JMapFieldType", "JMapField",
    "JMapEntry", "JMapInfo", "from_buffer", "pack_buffer", "from_file", "write_file", "from_csv", "dump_csv"
]

import csv
import enum
import os
import struct
import warnings


# ----------------------------------------------------------------------------------------------------------------------
# Exception for JMap-related actions
# ----------------------------------------------------------------------------------------------------------------------
class JMapException(Exception):
    """
    Signals that an error occurred during any JMap-related action.
    """
    pass


# ----------------------------------------------------------------------------------------------------------------------
# Hash lookup table implementations
# ----------------------------------------------------------------------------------------------------------------------
def calc_old_hash(field_name: str) -> int:
    """
    The old hash function that is used in Luigi's Mansion. The resulting hash is a 32-bit value. The field name is
    expected to be an ASCII-string.

    :param field_name: the field name to be hashed.
    :returns: the 32-bit hash value.
    """
    field_hash = 0

    for ch in field_name.encode("ascii"):
        ch |= ~0xFF if ch & 0x80 else 0  # Signed char
        field_hash = (((field_hash << 8) & 0xFFFFFFFF) + ch) % 33554393

    return field_hash


def calc_jgadget_hash(field_name: str) -> int:
    """
    The JGadget hash function that is used in the Super Mario Galaxy games and Donkey Kong Jungle Beat. The resulting
    hash is a 32-bit value. The field name is expected to be an ASCII-string.

    :param field_name: the field name to be hashed.
    :returns: the 32-bit hash value.
    """
    field_hash = 0

    for ch in field_name.encode("ascii"):
        ch |= ~0xFF if ch & 0x80 else 0  # Signed char
        field_hash = (field_hash * 31) + ch

    return field_hash & 0xFFFFFFFF


class JMapHashTable:
    """
    A  hash lookup implementation for known field names. This stores a valid name string for a given hash. The actual
    hashing algorithm differs between the games and needs to be specified first. A file that lists known field names can
    be used to initialize the hash table.
    """

    def __init__(self, hash_func, lookup_file_path):
        """
        Constructs a new hash table using the specified hash function and list file of known field names. Each line
        corresponds to a field that should be included. Lines that start with a '#' will be ignored and are treated as
        comments. This raises a FileNotFoundError if the lookup file does not exist.

        :param hash_func: the hashing function to be used.
        :param lookup_file_path: the file path containing the known field names.
        :raises FileNotFoundError: when the lookup file cannot be found.
        """
        self._hash_func_ = hash_func
        self._lookup_ = dict()

        if os.path.exists(lookup_file_path):
            for field in open(lookup_file_path, "r", encoding="utf-8").readlines():
                # Comment line?
                if field.startswith("#"):
                    continue

                field = field.strip("\r\n")
                self._lookup_[self.calc(field)] = field
        else:
            raise FileNotFoundError(f"Lookup names file \"{lookup_file_path}\" cannot be found!")

    def calc(self, field_name: str) -> int:
        """
        Calculates the hash value over a given field name. The resulting hash is a 32-bit value.

        :param field_name: the field name to be hashed.
        :returns: the 32-bit hash value.
        """
        return self._hash_func_(field_name)

    def find(self, field_hash: int) -> str:
        """
        Attempts to retrieve a valid field name for the specified hash value. If the hash is not found in the lookup
        table, it returns a hexadecimal representation of the hash. For example, if the hash value 0xDEADBEEF could not
        be found, this returns "[DEADBEEF]".

        :param field_hash: the hash to find the field name for.
        :returns: the field name if it exists, otherwise a hexadecimal string representation.
        """
        if field_hash in self._lookup_:
            return self._lookup_[field_hash]
        else:
            return f"[{field_hash:08X}]"

    def add(self, field_name: str) -> int:
        """
        Calculates the hash value for the specified field name tries to add the hash-name pair to the hash lookup table
        if it does not exist already. The hash will be returned as well.

        :param field_name: the string to calculate the hash for.
        :returns: the 32-bit hash value.
        """
        field_hash = self.calc(field_name)

        if field_hash not in self._lookup_:
            self._lookup_[field_hash] = field_name

        return field_hash


class SuperMarioGalaxyHashTable(JMapHashTable):
    """A hash table implementation for Super Mario Galaxy 1/2."""

    def __init__(self):
        """Constructs a new hash lookup table using the known field names from Super Mario Galaxy 1/2."""
        super().__init__(calc_jgadget_hash, os.path.join(os.path.dirname(__file__), "lookup_supermariogalaxy.txt"))


class JungleBeatHashTable(JMapHashTable):
    """A hash table implementation for Donkey Kong Jungle Beat."""

    def __init__(self):
        """Constructs a new hash lookup table using the known field names from Donkey Kong Jungle Beat."""
        super().__init__(calc_jgadget_hash, os.path.join(os.path.dirname(__file__), "lookup_donkeykongjunglebeat.txt"))


class SuperMarioSunshineHashTable(JMapHashTable):
    """A hash table implementation for Super Mario Sunshine."""

    def __init__(self):
        """Constructs a new hash lookup table using the known field names from Super Mario Sunshine."""
        super().__init__(calc_old_hash, os.path.join(os.path.dirname(__file__), "lookup_supermariosunshine.txt"))


class LuigisMansionHashTable(JMapHashTable):
    """A hash table implementation for Luigi's Mansion."""

    def __init__(self):
        """Constructs a new hash lookup table using the known field names from Luigi's Mansion."""
        super().__init__(calc_old_hash, os.path.join(os.path.dirname(__file__), "lookup_luigismansion.txt"))


# ----------------------------------------------------------------------------------------------------------------------
# Proper field type declarations
# ----------------------------------------------------------------------------------------------------------------------
class JMapFieldType(enum.Enum):
    """
    Declarations of all data types that are supported by JMapInfo containers. Every type holds information about their
    size in bytes, bitmask storage order, default value and data type.
    """

    def __new__(cls, *args, **kwargs):
        idx = len(cls.__members__)
        obj = object.__new__(cls)
        obj._value_ = idx
        return obj

    def __init__(self, size: int, mask: int, order: int, data_type, defval):
        self._size_ = size
        self._mask_ = mask
        self._order_ = order
        self._data_type_ = data_type
        self._default_ = defval

    @property
    def size(self) -> int:
        """The field data size in bytes."""
        return self._size_

    @property
    def mask(self) -> int:
        """The field data bitmask."""
        return self._mask_

    @property
    def order(self) -> int:
        """The sorting order index."""
        return self._order_

    @property
    def data_type(self):
        """The data type."""
        return self._data_type_

    @property
    def default(self):
        """The default data type value."""
        return self._default_

    LONG          =  4, 0xFFFFFFFF,  2, int, 0
    STRING        = 32, 0x00000000,  0, str, ""
    FLOAT         =  4, 0xFFFFFFFF,  1, float, 0.0
    LONG_2        =  4, 0xFFFFFFFF,  3, int, 0
    SHORT         =  2, 0x0000FFFF,  4, int, 0
    CHAR          =  1, 0x000000FF,  5, int, 0
    STRING_OFFSET =  4, 0xFFFFFFFF,  6, str, ""


# ----------------------------------------------------------------------------------------------------------------------
# JMap field and entry definitions
# ----------------------------------------------------------------------------------------------------------------------
class JMapField:
    """
    A field (or column) of a JMapInfo container. This specifies the name, hash, data type, mask and shift amount for an
    individual field. Actual fields should be created by the JMapInfo instance itself. All entries in a JMapInfo should
    contain data for every field in the container.
    """

    # Structures for parsing and packing
    __STRUCT_BE__ = struct.Struct(">2IH2b")  # Big-endian
    __STRUCT_LE__ = struct.Struct("<2IH2b")  # Little-endian

    def __init__(self, jmap, field_hash: int = 0, field_type: JMapFieldType = None,
                 mask: int = 0xFFFFFFFF, shift_amount: int = 0, defval=None):
        """
        Low-level constructor for a new JMapField. The given JMapInfo container will be assigned to the field. This
        should not be called directly. Instead, use JMapInfo's methods for creating new fields.

        :param jmap: The JMapInfo container that this field belongs to.
        :param field_hash: The field's hash.
        :param field_type: The data type of this field.
        :param mask: The bitmask.
        :param shift_amount: The amount of bits to be shifted.
        :param defval: The default value for the field.
        """
        self._jmap_ = jmap
        self._hash_ = field_hash
        self._type_ = field_type
        self._mask_ = mask
        self._shift_ = shift_amount
        self._default_ = defval
        self._offset_ = 0

    @property
    def jmap(self):
        """The JMapInfo container that the field belongs to."""
        return self._jmap_

    @property
    def name(self) -> str:
        """The field's name."""
        return self._jmap_.hashtable.find(self._hash_)

    @property
    def hash(self) -> int:
        """The field's hash."""
        return self._hash_

    @property
    def type(self) -> JMapFieldType:
        """The field's data type."""
        return self._type_

    @property
    def mask(self) -> int:
        """The field's bitmask."""
        return self._mask_

    @property
    def shift(self) -> int:
        """The field's shift amount."""
        return self._shift_

    @property
    def default(self):
        """The field's default value."""
        return self._default_

    def __repr__(self):
        """Implements "repr(`self`)"."""
        return self._jmap_.hashtable.find(self._hash_)

    def _unpack_(self, data, off: int, is_big_endian: bool):
        """
        Unpacks the field's information from the specified buffer as defined in the BCSV specifications.

        :param data: the buffer.
        :param off: the offset into the buffer.
        :param is_big_endian: the endianness of the data.
        :raises JMapException: when an invalid field type is detected.
        """
        strct = self.__STRUCT_BE__ if is_big_endian else self.__STRUCT_LE__
        self._hash_, self._mask_, self._offset_, self._shift_, raw_type = strct.unpack_from(data, off)

        if raw_type < 0 or raw_type >= 7:  # Invalid or unknown type
            raise JMapException(f"Invalid JMap field type with ID 0x{raw_type:02X} found!")

        self._type_ = JMapFieldType(raw_type)
        self._default_ = self._type_.default

    def _pack_(self, data, off: int, is_big_endian: bool):
        """
        Packs the field's information into the specified buffer as defined in the BCSV specifications.

        :param data: the buffer.
        :param off: the offset into the buffer.
        :param is_big_endian: the endianness of the data.
        """
        strct = self.__STRUCT_BE__ if is_big_endian else self.__STRUCT_LE__
        strct.pack_into(data, off, self._hash_, self._mask_, self._offset_, self._shift_, self._type_.value)


class JMapEntry:
    """
    An entry (or row) of a JMapInfo container. This holds the actual data. Every entry should contain data for all the
    fields in a JMap container. The data is stored as hash-value pairs. However, data can be accessed using the field
    hash or name.
    """

    def __init__(self, jmap):
        """
        Constructs a new JMapEntry for the given JMapInfo container. This should not be called outside JMapInfo itself.
        Instead, use JMapInfo's methods for creating new entries.

        :param jmap: The JMapInfo container that this field belongs to.
        """
        self._jmap_ = jmap
        self._data_ = dict()

    @property
    def jmap(self):
        """The JMapInfo container that the entry belongs to."""
        return self._jmap_

    def data(self):
        """Returns a view of hash-value pairs."""
        return self._data_.items()

    def __repr__(self):
        """Implements "repr(`self`)"."""
        string = "{"
        first = True

        for field_hash, value in self._data_.items():
            if not first:
                string += ", "
            else:
                first = False
            string += repr(self._jmap_.hashtable.find(field_hash)) + ": " + repr(value)

        return string + "}"

    def __len__(self):
        """Implements "len(`self`)"."""
        return len(self._data_)

    def __getitem__(self, field_key):
        """Implements "`self`[`field_key`]"."""
        if isinstance(field_key, str):
            field_hash = self._jmap_.hashtable.calc(field_key)

            if field_hash not in self._data_:
                raise KeyError(f"Entry does not contain the field \"{field_key}\"")
            else:
                return self._data_[field_hash]
        elif isinstance(field_key, int):
            if field_key not in self._data_:
                raise KeyError(f"Entry does not contain the field [{field_key:08X}]")
            else:
                return self._data_[field_key]
        else:
            raise TypeError("Key must be a str or int!")

    def __setitem__(self, field_key, value):
        """Implements "`self`[`field_key`] = `value`"."""
        if isinstance(field_key, str):
            field_hash = self._jmap_.hashtable.calc(field_key)

            if field_hash not in self._data_:
                raise KeyError(f"Entry does not contain the field \"{field_key}\"")
            elif type(self._data_[field_hash]) != type(value):
                raise TypeError(f"Wrong data type for field \"{field_key}\": Expected {str(type(self._data_[field_hash]))}, found {type(value)} instead.")
            else:
                self._data_[field_hash] = value
        elif isinstance(field_key, int):
            if field_key not in self._data_:
                raise KeyError(f"Entry does not contain the field [{field_key:08X}]")
            elif type(self._data_[field_key]) != type(value):
                raise TypeError(f"Wrong data type for field [{field_key:08X}]: Expected {str(type(self._data_[field_key]))}, found {type(value)} instead.")
            else:
                self._data_[field_key] = value
        else:
            raise TypeError("Key must be a str or int!")

    def __contains__(self, field_key):
        """Implements "`field_key` in `self`"."""
        if isinstance(field_key, str):
            return self._jmap_.hashtable.calc(field_key) in self._data_
        elif isinstance(field_key, int):
            return field_key in self._data_
        else:
            raise TypeError("Key must be a str or int!")


# ----------------------------------------------------------------------------------------------------------------------
# JMapInfo implementation according to the BCSV / JMap format
# ----------------------------------------------------------------------------------------------------------------------
class JMapInfo:
    """
    The table-like JMap container that consists of individual fields and entries. Provides high-level access to entries.
    A hash lookup table is used to retrieve proper names for fields.
    """

    # Structures for parsing and packing
    __STRUCT_BE__ = struct.Struct(">4I")  # Big-endian
    __STRUCT_LE__ = struct.Struct("<4I")  # Little-endian

    def __init__(self, hashtable: JMapHashTable):
        """
        Constructs a new JMapInfo container with no fields or entries. The specified lookup hash table will be used to
        retrieve proper names for hashes.

        :param hashtable: the hash lookup table to be used.
        """
        self._fields_ = dict()        # hash-field pairs that describe the contents of an entry.
        self._entries_ = list()       # List of actual entries.
        self._hashtable_ = hashtable  # The lookup hashtable that is used to retrieve proper field names.
        self._entry_size_ = -1        # Size of a single entry. Negative value forces recalculation of total size.

    @property
    def hashtable(self):
        """Returns the hash lookup table used by this container."""
        return self._hashtable_

    @property
    def fields(self) -> tuple:
        """
        Returns a tuple of all fields in this container.

        :return: the tuple of all fields.
        """
        return tuple(self._fields_.values())

    def __iter__(self):
        """Implements "iter(`self`)"."""
        return iter(self._entries_)

    def __reversed__(self):
        """Implements "reversed(`self`)"."""
        return reversed(self._entries_)

    def __repr__(self):
        """Implements "repr(`self`)"."""
        return repr(self._entries_)

    def __len__(self):
        """Implements "len(`self`)"."""
        return len(self._entries_)

    def __getitem__(self, key):
        """Implements "`self`[`key`]"."""
        return self._entries_[key]

    def __delitem__(self, key):
        """Implements "del `self`[`key`]"."""
        if isinstance(key, slice):
            for i in reversed(range(*key.indices(len(self._entries_)))):
                self._entries_[i]._jmap_ = None
                del self._entries_[i]
        else:
            self._entries_[key]._jmap_ = None
            del self._entries_[key]

    def __contains__(self, field_key):
        """Implements "`field_key` in `self`"."""
        if isinstance(field_key, str):
            return self._hashtable_.calc(field_key) in self._fields_
        elif isinstance(field_key, int):
            return field_key in self._fields_
        else:
            raise TypeError("Key must be a str or int!")

    def get_field(self, field_key) -> JMapField:
        """
        Retrieves the field using the specified key (hash or name) and remove's the field's data from all entries.

        :param field_key: the field's key (hash or name).
        :return: the field that corresponds to the key.
        """
        if isinstance(field_key, str):
            field_hash = self._hashtable_.calc(field_key)

            if field_hash not in self._fields_:
                raise KeyError(f"Entry does not contain the field \"{field_key}\"")
            else:
                return self._fields_[field_hash]
        elif isinstance(field_key, int):
            if field_key not in self._fields_:
                raise KeyError(f"Entry does not contain the field [{field_key}]")
            else:
                return self._fields_[field_key]
        else:
            raise TypeError("Key must be a str or int!")

    def create_field(self, field_name, field_type: JMapFieldType, defval, mask: int = -1, shift_amount: int = 0):
        """
        Creates a new field with the given name, type, mask and shift amount. This also sets the field's data to the
        default value for every entry. If a field with the same hash already exists, a JMapException will be raised.

        :param field_name: the new field's name.
        :param field_type: the new field's data type.
        :param defval: the new field's default value.
        :param mask: the new field's bitmask. If negative, the field type's default mask will be used.
        :param shift_amount: the new field's shift amount.
        :raises JMapException: if a field with the same hash already exists.
        """
        if not isinstance(defval, field_type.data_type):
            raise TypeError(f"Default value type {repr(type(defval))} is not expected type {repr(field_type.data_type)}!")

        # Calculate hash and check if field with same hash already exists
        field_hash = self._hashtable_.add(field_name)

        if field_hash in self._fields_:
            raise JMapException(f"Field \"{field_name}\" already exists!")

        # Create the actual field
        mask = field_type.mask if mask < 0 else mask
        field = JMapField(self, field_hash, field_type, mask, shift_amount, defval)

        # Add the new field and force recalculation of entry size
        self._fields_[field_hash] = field
        self._entry_size_ = -1

        # Set default values for all entries
        for entry in self._entries_:
            entry._data_[field_hash] = field.default

    def drop_field(self, field_key):
        """
        Drops the field (column) with the specified key (hash or name) and remove's the field's data from all entries.

        :param field_key: the field's key (hash or name).
        """
        def dropfield0(field_hash):
            field = self._fields_[field_hash]
            field._jmap_ = None  # Unlink
            del self._fields_[field_hash]

            self._entry_size_ = -1
            for entry in self._entries_:
                del entry._data_[field_hash]

        if isinstance(field_key, str):
            field_hash = self._hashtable_.calc(field_key)

            if field_hash not in self._fields_:
                raise KeyError(f"Field \"{field_key}\" does not exist!")
            else:
                dropfield0(field_hash)
        elif isinstance(field_key, int):
            if field_key not in self._fields_:
                raise KeyError(f"Field [{field_key:08X}] does not exist!")
            else:
                dropfield0(field_key)
        else:
            raise TypeError("Key must be a str or int!")

    def create_entry(self) -> JMapEntry:
        """
        Creates a new entry, populates it with default values for all fields and appends it at the end of the container.

        :return: the newly created entry.
        """
        entry = JMapEntry(self)

        for field in self._fields_.values():
            entry._data_[field.hash] = field.default

        self._entries_.append(entry)

        return entry

    def remove_entry(self, index: int):
        """
        Removes and unlinks the entry at the given index.

        :param index: the entry's index.
        """
        entry = self._entries_[index]
        entry._jmap_ = None
        del self._entries_[index]

    def clear_entries(self):
        """
        Removes and unlinks all entries from this container.
        """
        for entry in self._entries_:
            entry._jmap_ = None

        self._entries_.clear()

    def sort_entries(self, key, reverse: bool = False):
        """
        Sorts the entries using the given sorting key.

        :param key: the sorting key function.
        :param reverse: reverse sorting order.
        """
        self._entries_.sort(key=key, reverse=reverse)

    def copy(self):
        clone = JMapInfo(self._hashtable_)
        clone._entry_size_ = self._entry_size_

        for field_hash, field in self._fields_.items():
            clone_field = JMapField(clone, field_hash, field.type, field.mask, field.shift, field.default)
            clone._fields_[field_hash] = clone_field

        for entry in self._entries_:
            clone_entry = JMapEntry(clone)
            clone_entry._data_ = entry._data_.copy()
            clone._entries_.append(clone_entry)

        return clone

    __copy__ = copy
    __deepcopy__ = copy

    def _unpack_(self, data, off: int, is_big_endian: bool, encoding: str):
        """
        Unpacking the content from the specified buffer. The data is expected to be stored in the BCSV format.

        :param data: the byte buffer.
        :param off: the offset into the buffer.
        :param is_big_endian: the endianness of the data.
        :param encoding: the encoding for strings.
        """
        # Unpack header and calculate string pool offset
        strct = self.__STRUCT_BE__ if is_big_endian else self.__STRUCT_LE__
        num_entries, num_fields, off_data, self._entry_size_ = strct.unpack_from(data, off)
        off_strings = off + off_data + (num_entries * self._entry_size_)

        # Unpack fields
        off_tmp = off + 0x10

        for i in range(num_fields):
            field = JMapField(self)
            field._unpack_(data, off_tmp, is_big_endian)
            self._fields_[field.hash] = field
            off_tmp += 0xC

        # Unpack entries
        off_tmp = off + off_data
        endian = ">" if is_big_endian else "<"

        for i in range(num_entries):
            entry = JMapEntry(self)

            for field in self._fields_.values():
                field_type = field.type
                off_val = off_tmp + field._offset_
                val = None

                # Read long
                if field_type == JMapFieldType.LONG or field_type == JMapFieldType.LONG_2:
                    val = (struct.unpack_from(endian + "I", data, off_val)[0] & field.mask) >> field.shift
                    val |= ~0xFFFFFFFF if val & 0x80000000 else 0

                # Read string
                elif field_type == JMapFieldType.STRING:
                    # Read 32 bytes maximum
                    end = data.index(0x00, off_val, off_val + 32)
                    end = 32 if end < 0 else end
                    val = data[off_val:end].decode(encoding)

                # Read float
                elif field_type == JMapFieldType.FLOAT:
                    val = struct.unpack_from(endian + "f", data, off_val)[0]

                # Read short
                elif field_type == JMapFieldType.SHORT:
                    val = (struct.unpack_from(endian + "H", data, off_val)[0] & field.mask) >> field.shift
                    val |= ~0xFFFF if val & 0x8000 else 0

                # Read char
                elif field_type == JMapFieldType.CHAR:
                    val = (data[off_val] & field.mask) >> field.shift
                    val |= ~0xFF if val & 0x80 else 0

                # Read string at offset
                elif field_type == JMapFieldType.STRING_OFFSET:
                    off_val = off_strings + struct.unpack_from(endian + "I", data, off_val)[0]
                    end_str = off_val

                    while data[end_str]:
                        end_str += 1

                    val = data[off_val:end_str].decode(encoding)

                entry._data_[field.hash] = val

            self._entries_.append(entry)
            off_tmp += self._entry_size_

    def makebin(self, is_big_endian: bool, encoding: str) -> bytearray:
        """
        Packs the container's contents according to the BCSV format and returns the resulting bytearray buffer.

        :param is_big_endian: the endianness of the data.
        :param encoding: the encoding for strings.
        :return: the packed bytearray buffer.
        """
        # Prepare header information
        num_entries = len(self._entries_)
        num_fields = len(self._fields_)
        off_data = 0x10 + num_fields * 0xC

        # Calculate entry size and field offsets
        if self._entry_size_ < 0:
            len_data_entry = 0

            for field in sorted(self._fields_.values(), key=lambda k: k.type.order):
                field._offset_ = len_data_entry
                len_data_entry += field.type.size

            # Align total entry size to 4 bytes
            self._entry_size_ = len_data_entry + 3 & ~3

        # Prepare output buffer and write header
        buffer = bytearray(off_data + num_entries * self._entry_size_)
        strct = self.__STRUCT_BE__ if is_big_endian else self.__STRUCT_LE__
        strct.pack_into(buffer, 0, num_entries, num_fields, off_data, self._entry_size_)

        # Pack fields
        off_tmp = 0x10

        for field in self._fields_.values():
            field._pack_(buffer, off_tmp, is_big_endian)
            off_tmp += 0xC

        # Pack entries and prepare the string pool
        off_strings = len(buffer)
        string_offsets = dict()
        endian = ">" if is_big_endian else "<"

        for entry in self._entries_:
            for field in self._fields_.values():
                field_type = field.type
                off_val = off_tmp + field._offset_
                val = entry._data_[field.hash]

                # Pack long
                if field_type == JMapFieldType.LONG or field_type == JMapFieldType.LONG_2:
                    struct.pack_into(endian + "I", buffer, off_val, (val << field.shift) & field.mask)

                # Pack string
                elif field_type == JMapFieldType.STRING:
                    enc_string = val.encode(encoding)
                    if len(enc_string) >= 32:
                        warnings.warn("String is too long to be embedded. String will be chopped to fit 32 bytes!")
                    len_string = min(len(enc_string), 31)  # Last byte is for null-terminator
                    buffer[off_val:off_val + len_string] = enc_string[:len_string]

                # Pack float
                elif field_type == JMapFieldType.FLOAT:
                    struct.pack_into(endian + "f", buffer, off_val, val)

                # Pack short
                elif field_type == JMapFieldType.SHORT:
                    struct.pack_into(endian + "H", buffer, off_val, (val << field.shift) & field.mask)

                # Pack char
                elif field_type == JMapFieldType.CHAR:
                    buffer[off_val] = (val << field.shift) & field.mask

                # Pack string at offset
                elif field_type == JMapFieldType.STRING_OFFSET:
                    if val in string_offsets:
                        off_string = string_offsets[val]
                    else:
                        off_string = len(buffer) - off_strings
                        string_offsets[val] = off_string
                        buffer += (val + "\0").encode(encoding)

                    struct.pack_into(endian + "I", buffer, off_val, off_string)

            off_tmp += self._entry_size_

        # Align buffer to 32 bytes
        len_buf = len(buffer)
        buffer += bytearray([0x40] * ((len_buf + 31 & ~31) - len_buf))

        return buffer


# ----------------------------------------------------------------------------------------------------------------------
# Helper I/O functions
# ----------------------------------------------------------------------------------------------------------------------
def from_buffer(hashtable: JMapHashTable, buffer, offset: int, big_endian: bool = True, encoding: str = "shift_jisx0213") -> JMapInfo:
    """
    Creates and returns a new JMapInfo container by unpacking the content from the specified buffer. The data is
    expected to be stored in the JMap / BCSV format.

    :param hashtable: the hash lookup table to be used.
    :param buffer: the byte buffer.
    :param offset: the offset into the buffer.
    :param big_endian: the endianness of the data.
    :param encoding: the encoding for strings.
    :return: the unpacked JMapInfo container.
    """
    jmap = JMapInfo(hashtable)
    jmap._unpack_(buffer, offset, big_endian, encoding)
    return jmap


def pack_buffer(jmap: JMapInfo, big_endian: bool = True, encoding: str = "shift_jisx0213") -> bytearray:
    """
    Packs the given JMapInfo's contents according to the BCSV format and returns the resulting bytearray buffer.

    :param jmap: the JMapInfo container.
    :param big_endian: the endianness of the data.
    :param encoding: the encoding for strings.
    :return: the buffer containing the stored data.
    """
    return jmap.makebin(big_endian, encoding)


def from_file(hashtable: JMapHashTable, file_path: str, big_endian: bool = True, encoding: str = "shift_jisx0213") -> JMapInfo:
    """
    Creates and returns a new JMapInfo container by unpacking the contents from the given file path. The data is
    expected to be stored in the JMap / BCSV format.

    :param hashtable: the hash lookup table to be used.
    :param file_path: the file path to the JMap / BCSV file.
    :param big_endian: the endianness of the data.
    :param encoding: the encoding for strings.
    :return: the unpacked JMapInfo container.
    """
    jmap = JMapInfo(hashtable)
    with open(file_path, "rb") as f:
        jmap._unpack_(f.read(), 0, big_endian, encoding)
    return jmap


def write_file(jmap: JMapInfo, file_path: str, big_endian: bool = True, encoding: str = "shift_jisx0213"):
    """
    Packs the given JMapInfo's contents according to the BCSV format and writes the resulting buffer's contents to the
    specified file.

    :param jmap: the JMapInfo container.
    :param file_path: the file path to write the contents to.
    :param big_endian: the endianness of the data.
    :param encoding: the encoding for strings.
    """
    buffer = jmap.makebin(big_endian, encoding)

    with open(file_path, "wb") as f:
        f.write(buffer)
        f.flush()


__CSV_FIELD_TYPES__ = ["Int", "EmbeddedString", "Float", "Int2", "Short", "Char", "String"]
__CSV_FIELD_DEFAULTS__ = ["0", "0", "0.0", "0", "0", "0", "0"]
__CSV_FIELD_PRIMARIES__ = [int, str, float, int, int, int, str]


def from_csv(hashtable: JMapHashTable, file_path: str, encoding: str = "utf-8") -> JMapInfo:
    """
    Creates a new JMapInfo container using the raw CSV data found in the specified file. The CSV files have to be comma-
    delimited and may use quote marks for quotes strings. The information of each field consists of three components
    that are separated by double-colons. Example: GroupName:String:0. The components describe the field's name, type and
    default value, respectively.

    :param hashtable: the hash lookup table to be used.
    :param file_path: the file path to the CSV file.
    :param encoding: the CSV file's encoding, expects utf-8 by default.
    :return: the created JMapInfo container.
    """
    jmap = JMapInfo(hashtable)

    with open(file_path, "r", encoding=encoding, newline="") as f:
        csvreader = csv.reader(f, delimiter=",", quotechar='"')

        # Create fields
        field_descs = next(csvreader, None)

        if field_descs is None:
            raise SyntaxError("CSV file is empty.")

        for field_desc in field_descs:
            # Get field descriptor information
            field_desc = field_desc.split(":")

            if len(field_desc) != 3:
                raise SyntaxError("Number of field descriptor details is not 3!")

            field_name, field_type, field_default = field_desc

            if len(field_name) == 0:
                raise SyntaxError("Field name cannot be empty!")

            # Get proper JMapFieldType and default value from descriptor
            if field_type == "Int":
                actual_type = JMapFieldType.LONG
                actual_default = int(field_default)
            elif field_type == "EmbeddedString":
                actual_type = JMapFieldType.STRING
                actual_default = ""
            elif field_type == "Float":
                actual_type = JMapFieldType.FLOAT
                actual_default = float(field_default)
            elif field_type == "Int2":
                actual_type = JMapFieldType.LONG_2
                actual_default = int(field_default)
            elif field_type == "Short":
                actual_type = JMapFieldType.SHORT
                actual_default = int(field_default)
            elif field_type == "Char":
                actual_type = JMapFieldType.CHAR
                actual_default = int(field_default)
            elif field_type == "String":
                actual_type = JMapFieldType.STRING_OFFSET
                actual_default = ""
            else:
                raise SyntaxError(f"Unknown CSV field type {field_type} for field {field_name}")

            # Check if field name is a hash
            if field_name[0] == "[" and field_name[-1] == "]":
                field_hash = int(field_name[1:-1], 16)
            else:
                field_hash = hashtable.add(field_name)

            field = JMapField(jmap, field_hash, actual_type, actual_type.mask, 0, actual_default)
            jmap._fields_[field.hash] = field

        # Create entries
        for entry_row in csvreader:
            entry = JMapEntry(jmap)
            jmap._entries_.append(entry)

            for i, field in enumerate(jmap._fields_.values()):
                val = field.default if len(entry_row[i]) == 0 else __CSV_FIELD_PRIMARIES__[field.type.value](entry_row[i])
                entry._data_[field.hash] = val

    return jmap


def dump_csv(jmap: JMapInfo, file_path: str, encoding: str = "utf-8"):
    """
    Dumps the JMapInfo's data to the specified CSV file. The CSV file is comma-delimited and may use quote marks for
    quoted strings.

    :param jmap: the JMapInfo container.
    :param file_path: the file path to the CSV file.
    :param encoding: the CSV file's encoding, expects utf-8 by default.
    """
    with open(file_path, "w", encoding=encoding, newline="") as f:
        csvwriter = csv.writer(f, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL)

        # Write fields header
        field_descs = [
            f"{field.name}:{__CSV_FIELD_TYPES__[field.type.value]}:{__CSV_FIELD_DEFAULTS__[field.type.value]}"
            for field in jmap._fields_.values()
        ]
        csvwriter.writerow(field_descs)

        # Write entries
        for entry in jmap:
            csvwriter.writerow([str(entry[field.hash]) for field in jmap._fields_.values()])

        f.flush()
