def doi_to_filename(doi: str, filetype: str) -> str:
    return f"{doi.replace('/', '@')}.{filetype}"

def filename_to_doi(filename: str) -> str:
    return filename.rsplit(".", 1)[0].replace("@", "/")