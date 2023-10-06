# Installing iMolpro.app on macOS

Copy `iMolpro.app` to `/Applications` and launch in the usual way.  If system security mechanisms complain about a damaged app or similar, you can usually override them with, from the command line,

```
xattr -d com.apple.quarantine /Applications/iMolpro.app
```