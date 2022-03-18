import argparse
from . import jmap


LOOKUP_TABLES = {
    "smg": jmap.SuperMarioGalaxyHashTable,
    "dkjb": jmap.JungleBeatHashTable,
    "lm": jmap.LuigisMansionHashTable
}


def dump(args):
    jmap_enc = args.jmap_encoding if args.jmap_encoding else "shift_jisx0213"
    csv_enc = args.csv_encoding if args.csv_encoding else "utf-8"

    data = jmap.from_file(LOOKUP_TABLES[args.lookup](), args.jmap, not args.little_endian, jmap_enc)
    jmap.dump_csv(data, args.csv, csv_enc)
    print("Successfully dumped data to CSV file.")


def pack(args):
    jmap_enc = args.jmap_encoding if args.jmap_encoding else "shift_jisx0213"
    csv_enc = args.csv_encoding if args.csv_encoding else "utf-8"

    data = jmap.from_csv(LOOKUP_TABLES[args.lookup](), args.csv, csv_enc)
    jmap.write_file(data, args.jmap, not args.little_endian, jmap_enc)
    print("Successfully packed JMap data.")


def main():
    parser = argparse.ArgumentParser(description="")
    subs = parser.add_subparsers(dest="command", help="Command")
    subs.required = True

    dump_parser = subs.add_parser("tocsv", description="Dump JMap data to CSV file.")
    pack_parser = subs.add_parser("tojmap", description="Pack CSV file as JMap data.")

    for sub_parser in [dump_parser, pack_parser]:
        sub_parser.add_argument("-le", "--little_endian", action="store_true", help="Data is little-endian?")
        sub_parser.add_argument("-jmapenc", "--jmap_encoding", help="JMap file encoding. Default is shift_jisx0213."),
        sub_parser.add_argument("-csvenc", "--csv_encoding", help="CSV file encoding. Default is utf-8"),
        sub_parser.add_argument("lookup", choices=["smg", "dkjb", "lm"], help="The hash lookup table to use.")

    dump_parser.add_argument("jmap", help="Path to JMap data.")
    dump_parser.add_argument("csv", help="Path to CSV file.")
    dump_parser.set_defaults(func=dump)

    pack_parser.add_argument("csv", help="Path to CSV file.")
    pack_parser.add_argument("jmap", help="Path to JMap data.")
    pack_parser.set_defaults(func=pack)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
