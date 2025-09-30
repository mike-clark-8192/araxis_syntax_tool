# TODO

The tool can currently read and write Araxis syntax definition blobs from the filesystem.

We want to be able to read and write directly to the Windows registry.

Proposal:

Wherever a filename is accepted by the tool, and the purpose of that filename is to point the tool at an Araxis syntax blob, the tool now also accepts a specifier like this:

reg:[araxis_version]

`[araxis_version]` defaults to the latest version available in the registry]

For example, if we have:
```
Key: HKEY_CURRENT_USER\SOFTWARE\Araxis\Merge\7.0
Value: SyntaxHighlightingGeneric
Data: json:{<araxis_blob>}
DataType: REG_SZ
```
and
```
Key: HKEY_CURRENT_USER\SOFTWARE\Araxis\Merge\7.1
Value: SyntaxHighlightingGeneric
Data: json:{<araxis_blob>}
DataType: REG_SZ
```

Present in the registry, then we would default to reading/writing to the 7.1 key path. Otherwise the user may specify:
`reg:7.0` or `reg:7.1` (for example). If the key doesn't exist, the program should exit with an explanatory error,
because that version of Araxis Merge probably is not installed.

# Implementation notes

Probably use the `winreg` module that ships with Python.
https://docs.python.org/3/library/winreg.html
