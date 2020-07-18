# shlabber.py - Archives a soup

Schlabbern is like auslöffeln, only much more messy

## Features
 * Works with endless scroll
 * Saves more than images
 * Preserves some metadata
 * If your soup shows timestamps, they will be used to sort the backup

## Dependencies
 * virtualenv
 * python3

To install this, run:

```sh
virtualenv venv
./venv/bin/pip install -r requirements.txt
```

## Use
Basic usage:
```
venv/bin/python3 ./schlabber <name of soup>
```
If invoked without any parameters, the programm will asume the output direcory for all files is the
working directory.
To choose an alternative output diectory supply -d \<path> to the application

For more options:
```
./venv/bin/python3 ./schlabber -h
```

### Saving Video posts

Unfortunately, soup's display of video posts is broken, which is why we can't save them. But! If you are allowed to edit posts on a soup that you're saving, you can tell schlabber your soup session cookie & it'll save the source (embed or URL) for video links, as well:

1. Visit the soup you're saving in a logged-in browser.
2. Open your browser's dev tools and inspect cookies that are set on the page.
3. Find the `soup_session_id` cookie and copy that hex value.
4. Then, run the following (and replace `00000000deadbeef0000` with your session ID that you copied):

```
./venv/bin/python3 ./schlabber -s 00000000deadbeef0000 mysoup
```
