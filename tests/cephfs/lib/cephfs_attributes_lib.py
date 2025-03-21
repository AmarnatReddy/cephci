import base64
import json
import os
import random
import re
import string
import unicodedata

from tests.cephfs.cephfs_utilsV1 import FsUtils
from utility.log import Log

log = Log(__name__)


class CephFSAttributeUtilities(object):
    def __init__(self, ceph_cluster):
        self.ceph_cluster = ceph_cluster
        self.fs_util = FsUtils(ceph_cluster)

        self.mons = self.fs_util.mons
        self.mgrs = self.fs_util.mgrs
        self.osds = self.fs_util.osds
        self.mdss = self.fs_util.mdss
        self.clients = self.fs_util.clients
        self.installer = self.fs_util.installer

    def set_attributes(self, client, directory, **kwargs):
        """
        Set attributes for case sensitivity, normalization, and encoding.
        Usage: set_attributes("/mnt/dir", casesensitive=True, normalization="nfd", encoding="utf8")

        Args:
            directory (str): The path to the directory.
            **kwargs: Key-value pairs of attributes to set. Supported attributes:
                - casesensitive (bool): Enable or disable case sensitivity.
                - normalization (str): Set normalization (e.g., "nfd", "nfc").
                - encoding (str): Set encoding format (e.g., "utf8").

        Raises:
            ValueError: If an unsupported attribute is passed.

        """
        supported_attributes = ["casesensitive", "normalization", "encoding"]
        for key, value in kwargs.items():
            if key not in supported_attributes:
                raise ValueError(
                    "Unsupported attribute: {}. Supported attributes are {}".format(
                        key, supported_attributes
                    )
                )
            cmd = "setfattr -n ceph.dir.{} -v {} {}".format(key, value, directory)
            log.debug(cmd)
            client.exec_command(sudo=True, cmd=cmd)
            log.info("Set {} to {} on {}".format(key, value, directory))

    def get_charmap(self, client, directory):
        """Retrieve charmap attributes and return them as a dictionary.
        Args:
            directory (str): The path to the directory.

        Returns:
            dict: A dictionary containing the charmap attributes.
                Example:
                {
                    "casesensitive": False,
                    "normalization": "nfd",
                    "encoding": "utf8"
                }

        Example:
            >>> get_charmap("/mnt/mani-fs-2-client2/Dir1/")
            {
                "casesensitive": False,
                "normalization": "nfd",
                "encoding": "utf8"
            }
        """
        cmd = "getfattr -n ceph.dir.charmap {} --only-values".format(directory)
        out, _ = client.exec_command(sudo=True, cmd=cmd, check_ec=False)
        try:
            # Extract JSON using regex to handle unexpected shell prompt artifacts
            json_match = re.search(r"(\{.*\})", out.strip())
            if json_match:
                charmap_str = json_match.group(1)
                log.info("Charmap output for cmd {}: {}".format(cmd, charmap_str))
                return json.loads(charmap_str)
            else:
                log.info("Failed to extract JSON from charmap output: {}".format(out))
                raise ValueError("Invalid charmap output")
        except Exception:
            log.error("Failed to parse charmap for {}".format(directory))
            return {}

    def compare_charmaps(self, client, charmap1, charmap2):
        """Compare two charmap dictionaries and return if they match.
        Args:
            charmap1 (dict): The first charmap dictionary.
            charmap2 (dict): The second charmap dictionary.

        Returns:
            bool: True if both charmaps are identical, False otherwise.

        Example:
            >>> charmap1 = {"casesensitive": False, "normalization": "nfd", "encoding": "utf8"}
            >>> charmap2 = {"casesensitive": False, "normalization": "nfd", "encoding": "utf8"}
            >>> compare_charmaps(charmap1, charmap2)
            True

            >>> charmap3 = {"casesensitive": True, "normalization": "nfc", "encoding": "utf8"}
            >>> compare_charmaps(charmap1, charmap3)
            False
        """
        return charmap1 == charmap2

    def update_required_client_features(self, client, fs_name):
        """Update the required client feature attribute for a Ceph filesystem.

        Args:
            fs_name (str): The name of the Ceph filesystem to update.

        Returns:
            None
        """
        cmd = "ceph fs required_client_features {} add charmap".format(fs_name)
        client.exec_command(sudo=True, cmd=cmd)
        log.info("Updated client feature for {}".format(fs_name))

    def create_directory(self, client, path, force=False):
        """Create a directory, including parent directories if needed.

        Args:
            path (str): The full path of the directory to create.

        Example:
            create_directory("/mnt/cephfs/subdir1/subdir2")
            # This will execute: mkdir -p /mnt/cephfs/subdir1/subdir2
        """
        cmd = "mkdir {} {}".format("-p" if force else "", path)
        client.exec_command(sudo=True, cmd=cmd)
        log.info("Created directory: {}".format(path))

    def create_special_character_directories(self, client, base_path, count=1):
        """Create directories with a mix of special characters.
        Args:
            base_path (str): The parent directory where the new directories will be created.
            count (int, optional): The number of directories to create. Defaults to 1.

        Returns:
            None
        """
        special_chars = "@#$%^&*()-_=+[]{}|;:'\",<>?/"
        for _ in range(count):
            dir_name = "".join(
                random.choices(
                    string.ascii_letters + string.digits + special_chars,
                    k=random.randint(1, 255),
                )
            )
            full_path = os.path.join(base_path, dir_name)
            self.create_directory(client, full_path)
            log.info("Created special character directory: {}".format(full_path))

    def delete_directory(self, client, dir_path, recursive=False):
        """
        Delete a directory at the specified path.

        Args:
            dir_path (str): The full path of the directory to delete.
            recursive (bool): If True, delete directory and contents recursively. Defaults to False.

        Returns:
            bool: True if deletion was successful, False otherwise.
        """
        cmd = "rm {} {}".format("-rf" if recursive else "-f", dir_path)
        client.exec_command(sudo=True, cmd=cmd)
        log.info("Deleted directory: {} (recursive={})".format(dir_path, recursive))
        return True

    def create_file(self, client, file_path, content=None):
        """
        Create a file in the specified directory with optional content.

        Args:
            file_path (str): The path of the file to create.
            content (str, optional): Content to write to the file. Defaults to None.

        Returns:
            str: The full path of the created file.
        """
        cmd = "touch {}".format(file_path)
        client.exec_command(sudo=True, cmd=cmd)
        log.info("Created file: {}".format(file_path))

        if content:
            cmd = "echo '{}' > {}".format(content, file_path)
            client.exec_command(sudo=True, cmd=cmd)
            log.info("Wrote content to file: {}".format(file_path))

        return file_path

    def delete_file(self, client, file_path):
        """
        Delete a file at the specified path.

        Args:
            file_path (str): The full path of the file to delete.

        Returns:
            bool: True if deletion was successful, False otherwise.
        """
        cmd = "rm -f {}".format(file_path)
        client.exec_command(sudo=True, cmd=cmd)
        log.info("Deleted file: {}".format(file_path))
        return True

    def check_ls_case_sensitivity(self, client, base_path, dir_name):
        """
        Check if 'ls' can retrieve a directory with different case variations.

        Args:
            base_path (str): The base path where the directory is located.
            dir_name (str): The original directory name.

        Returns:
            bool: True if 'ls' successfully lists the directory (case-insensitive),
                False if it fails (case-sensitive).
        """
        test_variations = [dir_name.lower(), dir_name.upper(), dir_name.swapcase()]

        for variant in test_variations:
            test_path = os.path.join(base_path, variant)
            cmd = "ls {}".format(test_path)
            out, rc = client.exec_command(sudo=True, cmd=cmd, check_ec=False)
            log.debug("ls output of {}/{}: {}".format(base_path, dir_name, out))

            if rc != 0:  # 'ls' failed
                log.info("Directory '{}' is inaccessible.".format(test_path))
                return False

        log.info("Directory '{}' is accessible with different cases.".format(dir_name))
        return True

    def create_links(self, client, target, link_name, link_type="soft"):
        """Create soft or hard links.
        Args:
            target (str): The file or directory to link to.
            link_name (str): The name of the link to be created.
            link_type (str, optional): Type of link to create.
                                       Use "soft" for a symbolic link (default)
                                       or "hard" for a hard link.
        """
        cmd = f'ln {"-s" if link_type == "soft" else ""} {target} {link_name}'
        client.exec_command(sudo=True, cmd=cmd)
        log.info("Created {} link: {} -> {}".format(link_type, link_name, target))

    def remove_attributes(self, client, directory, *attributes):
        """
        Remove specified attributes from a directory.

        Args:
            client: The client object to execute commands.
            directory (str): The path to the directory.
            *attributes: Attributes to remove. Supported attributes:
                - "casesensitive"
                - "normalization"
                - "encoding"
                - "charmap"

        Raises:
            ValueError: If an unsupported attribute is passed.
        """
        supported_attributes = ["casesensitive", "normalization", "encoding", "charmap"]
        for attribute in attributes:
            if attribute not in supported_attributes:
                raise ValueError(
                    "Unsupported attribute: {}. Supported attributes are {}".format(
                        attribute, supported_attributes
                    )
                )

            cmd = "setfattr -x ceph.dir.{} {}".format(attribute, directory)
            log.debug(cmd)
            client.exec_command(sudo=True, cmd=cmd)
            log.info("Removed {} from {}".format(attribute, directory))

    def generate_random_unicode_names(count=1):
        """
        Generate random directory names that change under Unicode normalization.

        Args:
            count (int): Number of names to generate. Default: 1

        Returns:
            list: A list of generated directory names.
        """
        characters = [
            "Ä",
            "é",
            "ü",
            "ô",
            "ñ",  # Accented characters
            "ﬁ",
            "ﬂ",
            "Æ",
            "œ",  # Ligatures
            "Ａ",
            "Ｂ",
            "Ｃ",  # Full-width letters
            "¹",
            "²",
            "³",  # Superscripts
            "ß",
            "Ω",
            "µ",  # Special cases
        ]

        names = []
        for _ in range(count):
            name_length = random.randint(3, 8)  # Random length between 3 and 8
            name = "".join(random.choices(characters, k=name_length))
            names.append(name)

        return names

    def validate_normalization(self, client, base_path, dir_name, norm_type):
        """check if dir names are normalized by the filesystem.

        Args:
            base_path (str): Directory where test directories are created.
            dir_name (str): Original directory name before normalization.
            norm_type (str): Expected normalization type (NFC, NFD, NFKC, NFKD).

        Returns:
            bool: True if the filesystem-normalized name matches the expected normalization.
        """
        cmd = "ls {}/{}".format(base_path, dir_name)
        out, _ = client.exec_command(sudo=True, cmd=cmd)

        retrieved_names = out.split("\n")
        normalized_expected = unicodedata.normalize(norm_type, dir_name)

        for name in retrieved_names:
            normalized_name = unicodedata.normalize(norm_type, name)
            if normalized_name == normalized_expected:
                return True  # Match found

        # If no match, log expected vs actual names
        log.error("Normalization mismatch in {}:".format(dir_name))
        log.error("Expected (Normalized): {}".format(normalized_expected))
        log.error("Actual Retrieved Names: {}".format(retrieved_names))

        return False

    def fetch_alternate_name(self, client, fs_name, dir_path):
        """
        Fetches a dictionary of file paths and their corresponding alternate names for a specified Ceph file system.

        This function identifies the active MDS (Metadata Server) node for the given file system, executes a command to
        dump the directory tree in JSON format, and extracts the 'path' and 'alternate_name' fields into a dictionary.

        Args:
            client (object): The client object used to execute remote commands on the Ceph cluster.
            fs_name (str): The name of the Ceph file system for which to fetch alternate names.

        Returns:
            dict: A dictionary where the keys are file paths and the values are the corresponding alternate names.
        """
        log.info(
            "Fetching the active MDS node for file system {fs_name}".format(
                fs_name=fs_name
            )
        )
        active_mds = self.fs_util.get_active_mdss(client, fs_name)
        log.info(active_mds)
        cmd = "ceph tell mds.{active_mds} dump tree {dir_path} 2 -f json".format(
            active_mds=active_mds[0], dir_path=dir_path
        )
        out, _ = client.exec_command(sudo=True, cmd=cmd)

        # Remove log lines using regex to isolate JSON
        cleaned_output = re.sub(r"^[^\[{]*", "", out).strip()

        # Load JSON data
        try:
            json_data = json.loads(cleaned_output)
        except json.JSONDecodeError:
            log.error("Failed to decode JSON from the cleaned output")
            log.error(cleaned_output)

        log.info("JSON dump: %s", cleaned_output)
        # Extract 'path' and 'alternate_name' as a dictionary
        alternate_name_dict = {
            dentry.get("path", ""): dentry.get("alternate_name", "")
            for inode in json_data
            for dirfrag in inode.get("dirfrags", [])
            for dentry in dirfrag.get("dentries", [])
        }
        log.info(
            "Dict of alternate names: {alternate_name_dict}".format(
                alternate_name_dict=alternate_name_dict
            )
        )
        return alternate_name_dict

    def validate_alternate_name(
        self, alternate_name_dict, relative_path, empty_name=False
    ):
        """
        Validates if the base64-decoded alternate name for a given path matches the path itself.

        Args:
            alternate_name_dict (dict): A dictionary containing relative paths as keys and
                                        their base64-encoded alternate names as values.
            relative_path (str): The relative path to validate.

        Returns:
            bool: True if the decoded alternate name matches the given path, False otherwise.
        """
        log.debug("Validating for the path: %s", relative_path)
        if alternate_name_dict.get(relative_path) and empty_name is False:
            alternate_name = alternate_name_dict[relative_path]
            # Decode the string
            decoded_bytes = base64.b64decode(alternate_name)

            # Convert bytes to string
            decoded_str = decoded_bytes.decode("utf-8")
            log.info("Decoded String: %s", decoded_str)
            if decoded_str.strip() == os.path.basename(relative_path).strip():
                log.info("Alternate name decoded successfully and matching")
                return True
            else:
                log.error("Alternate and decoded name not matching")
                return False
        elif empty_name is True:
            log.info("Expected the alternate name to be empty and it succeeded")
            return True
        log.error(
            "Path {} not found in the dict: {}".format(
                relative_path, alternate_name_dict
            )
        )
        return False
