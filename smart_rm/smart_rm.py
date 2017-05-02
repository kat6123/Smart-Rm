# -*- coding: utf-8 -*-
from os import (
    listdir,
    strerror,
    walk,
    access,
    W_OK
)
from mover import Mover
from os.path import (
    expanduser,
    isdir,
    abspath,
    basename,
    join,
    isfile
)
from error import (
    PermissionError,
    ExistError,
    ModeError
)
from logging import (
    # debug,
    # info,
    # warning,
    error
    # critical
)
from errno import (
    EISDIR,
    ENOTEMPTY
)
from basket import (
    BASKET_FILES_DIRECTORY,
    BASKET_INFO_DIRECTORY,
    INFO_SECTION,
    OLD_PATH_OPTION,
    REMOVE_DATE_OPTION,
    FILE_HASH_OPTION,
    INFO_FILE_EXPANSION,
    DEFAULT_BASKET_LOCATION,
    get_basket_files_and_info_paths,
    check_basket_and_make_if_not_exist
)
from datetime import datetime
from hashlib import sha256


class SmartRemover(object):
    def __init__(
            self,
            basket_location=expanduser(DEFAULT_BASKET_LOCATION),
            confirm_removal=lambda: True,
            mover=None,
            is_relevant_file_name=lambda: True
    ):
        self.basket_files_location,     # XXX
        self.basket_info_location =
        get_basket_files_and_info_paths(basket_location)

        if mover is None:
            self.mover = Mover()
        else:
            self.mover = mover

        self.confirm_removal = confirm_removal
        self.is_relevant_file_name = is_relevant_file_name

        self._trashinfo_config = ConfigParser()
        self._trashinfo_config.add_section(INFO_SECTION_NAME)

    def remove_file_or_empty_directory(self, item_path):
        if isdir(item_path) and listdir(item_path):
            raise ModeError(ENOTEMPTY, strerror(ENOTEMPTY), item_path)

        if self.is_relevant_file_name(
            item_path
        ) and self.confirm_removal(
            item_path
        ):
            if self.mover.move(item_path, self.basket_files_location):
                self.make_trash_info_file(item_path)

    def remove_tree(self, tree):
        if isfile(tree):
            self.remove(tree)
            return

        items_to_remove = []

        for root, dirs, files in walk(tree, topdown=False):
            items_in_root_to_remove = []
            root = abspath(root)

            for file_path in files:
                if self.is_relevant_file_name(
                    file_path
                ) and self.confirm_removal(
                    file_path
                ):
                    abs_path = join(root, basename(file))
                    items_in_root_to_remove.append(abs_path)

            if self.is_relevant_file_name(root) and self.confirm_removal(root):
                if set(listdir(root)).issubset(items_to_remove):
                    items_to_remove = (
                        list(set(items_to_remove) - set(listdir(root)))
                    )
                    items_to_remove.append(root)
                else:
                    items_to_remove.extend(items_in_root_to_remove)
                    break
            else:
                items_to_remove.extend(items_in_root_to_remove)

        for item_path in items_to_remove:
            if self.mover.move(item_path, self.basket_files_location):
                self.make_trash_info_file(item_path)

    def make_trash_info_file(self, old_path):
        trashinfo_file = join(
            self.basket_info_location,
            basename(old_path) + INFO_FILE_EXPANSION
        )

        self._trashinfo_config.set(                 # wrap in try catch
            INFO_SECTION_NAME, OLD_PATH_OPTION, abspath(old_path)
        )
        self._trashinfo_config.set(
            INFO_SECTION_NAME, REMOVE_DATE_OPTION, datetime.today()
        )
        self._trashinfo_config.set(
            INFO_SECTION_NAME, FILE_HASH_OPTION, sha256(old_path).hexdigest()
        )

        with open(trashinfo_file, "w") as fp:
                self._trashinfo_config.write(fp)


class AdvancedRemover(object):
    def __init__(
            self, basket_location=expanduser("~/.local/share/basket"),
            confirm_rm_always=False, not_confirm_rm=False,
            confirm_if_file_has_not_write_access=True,
            remove=""
    ):
        # XXX
        if confirm_rm_always:
            confirm_removal = AdvancedRemover._ask_remove
        elif not_confirm_rm:
            confirm_removal = lambda: True
        else:
            confirm_removal = AdvancedRemover._ask_if_file_has_not_write_access

        self.remover = SmartRemover(
            confirm_removal=confirm_removal,    # confirm_removal,
            move_file_to_basket=remove
        )

    def remove_list(
            self, paths_to_remove,
            verify_removal=lambda: True
    ):
        for path in paths_to_remove:
            try:
                verify_removal(path)
                self.remover.remove_tree(path)
            except (PermissionError, ExistError, ModeError) as why:
                error(why)

    def remove_files(self, paths_to_remove):
        self.remove_list(
            paths_to_remove,
            verify_removal=AdvancedRemover._verify_file_removal
        )

    def remove_directories(self, paths_to_remove):
        self.remove_list(
            paths_to_remove,
            verify_removal=AdvancedRemover._verify_directory_removal
        )

    def remove_trees(self, paths_to_remove):
        self.remove_list(paths_to_remove)

    @staticmethod
    def _verify_file_removal(file):
        if not isfile(file):
            raise ModeError(EISDIR, strerror(EISDIR), file)

    @staticmethod
    def _verify_directory_removal(directory):
        if isdir(directory) and listdir(directory):
            raise ModeError(ENOTEMPTY, strerror(ENOTEMPTY), directory)

    @staticmethod
    def _ask_if_file_has_not_write_access(path):
        if access(path, W_OK):
            return True
        elif AdvancedRemover._ask_remove(path, special_info="write-protected"):
            return True

        return False

    @staticmethod
    def _ask_remove(path, special_info=""):
        if isfile(path):
            what_remove = "file"
        else:
            what_remove = "directory"
        answer = raw_input(
            "Do you want to remove {0} {1} \"{2}\"?: "
            "".format(special_info, what_remove, path)
        )
        if answer == 'y':
            return True
