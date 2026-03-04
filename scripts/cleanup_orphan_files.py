from weave.uploads_routes import cleanup_orphan_files


if __name__ == "__main__":
    result = cleanup_orphan_files()
    print(result)
