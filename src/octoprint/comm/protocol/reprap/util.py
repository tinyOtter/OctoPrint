# coding=utf-8
from __future__ import absolute_import, unicode_literals, print_function, \
	division

__author__ = "Gina Häußge <osd@foosel.net>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2016 The OctoPrint Project - Released under terms of the AGPLv3 License"


from octoprint.comm.protocol.reprap.commands import Command

# noinspection PyCompatibility
from past.builtins import basestring

import copy

try:
	# noinspection PyCompatibility
	from queue import Queue
except:
	# noinspection PyCompatibility
	from Queue import Queue


regex_float_pattern = "[-+]?[0-9]*\.?[0-9]+"
regex_positive_float_pattern = "[+]?[0-9]*\.?[0-9]+"
regex_int_pattern = "\d+"


def strip_comment(line):
	if not ";" in line:
		# shortcut
		return line

	escaped = False
	result = []
	for c in line:
		if c == ";" and not escaped:
			break
		result += c
		escaped = (c == "\\") and not escaped
	return "".join(result).strip()


def process_gcode_line(line, offsets=None, current_tool=None):
	line = strip_comment(line).strip()
	if not len(line):
		return None

	#if offsets is not None:
	#	line = apply_temperature_offsets(line, offsets, current_tool=current_tool)

	return line

def normalize_command_handler_result(command, handler_results, tags_to_add=None):
	"""
	Normalizes a command handler result.

	Handler results can be either ``None``, a single result entry or a list of result
	entries.

	``None`` results are ignored, the provided ``command``, ``command_type``,
	``gcode``, ``subcode`` and ``tags`` are returned in that case (as single-entry list with
	one 5-tuple as entry).

	Single result entries are either:

	  * a single string defining a replacement ``command``
	  * a 1-tuple defining a replacement ``command``
	  * a 2-tuple defining a replacement ``command`` and ``command_type``
	  * a 3-tuple defining a replacement ``command`` and ``command_type`` and additional ``tags`` to set

	A ``command`` that is ``None`` will lead to the entry being ignored for
	the normalized result.

	The method returns a list of normalized result entries. Normalized result
	entries always are a 4-tuple consisting of ``command``, ``command_type``,
	``gcode`` and ``subcode``, the latter three being allowed to be ``None``. The list may
	be empty in which case the command is to be suppressed.

	Examples:
	    >>> normalize_command_handler_result("M105", None, "M105", None, None, None)
	    [(u'M105', None, u'M105', None, None)]
	    >>> normalize_command_handler_result("M105", None, "M105", None, None, "M110")
	    [(u'M110', None, u'M110', None, None)]
	    >>> normalize_command_handler_result("M105", None, "M105", None, None, ["M110"])
	    [(u'M110', None, u'M110', None, None)]
	    >>> normalize_command_handler_result("M105", None, "M105", None, None, ["M110", "M117 Foobar"])
	    [(u'M110', None, u'M110', None, None), (u'M117 Foobar', None, u'M117', None, None)]
	    >>> normalize_command_handler_result("M105", None, "M105", None, None, [("M110",), "M117 Foobar"])
	    [(u'M110', None, u'M110', None, None), (u'M117 Foobar', None, u'M117', None, None)]
	    >>> normalize_command_handler_result("M105", None, "M105", None, None, [("M110", "lineno_reset"), "M117 Foobar"])
	    [(u'M110', u'lineno_reset', u'M110', None, None), (u'M117 Foobar', None, u'M117', None, None)]
	    >>> normalize_command_handler_result("M105", None, "M105", None, None, [])
	    []
	    >>> normalize_command_handler_result("M105", None, "M105", None, None, ["M110", None])
	    [(u'M110', None, u'M110', None, None)]
	    >>> normalize_command_handler_result("M105", None, "M105", None, None, [("M110",), (None, "ignored")])
	    [(u'M110', None, u'M110', None, None)]
	    >>> normalize_command_handler_result("M105", None, "M105", None, None, [("M110",), ("M117 Foobar", "display_message"), ("tuple", "of", "unexpected", "length"), ("M110", "lineno_reset")])
	    [(u'M110', None, u'M110', None, None), (u'M117 Foobar', u'display_message', u'M117', None, None), (u'M110', u'lineno_reset', u'M110', None, None)]
	    >>> normalize_command_handler_result("M105", None, "M105", None, {"tag1", "tag2"}, ["M110", "M117 Foobar"])
	    [(u'M110', None, u'M110', None, set([u'tag1', u'tag2'])), (u'M117 Foobar', None, u'M117', None, set([u'tag1', u'tag2']))]
	    >>> normalize_command_handler_result("M105", None, "M105", None, {"tag1", "tag2"}, ["M110", "M105", "M117 Foobar"], tags_to_add={"tag3"})
	    [(u'M110', None, u'M110', None, set([u'tag1', u'tag2', u'tag3'])), (u'M105', None, u'M105', None, set([u'tag1', u'tag2'])), (u'M117 Foobar', None, u'M117', None, set([u'tag1', u'tag2', u'tag3']))]
	    >>> normalize_command_handler_result("M105", None, "M105", None, {"tag1", "tag2"}, ["M110", ("M105", "temperature_poll"), "M117 Foobar"], tags_to_add={"tag3"})
	    [(u'M110', None, u'M110', None, set([u'tag1', u'tag2', u'tag3'])), (u'M105', u'temperature_poll', u'M105', None, set([u'tag1', u'tag2', u'tag3'])), (u'M117 Foobar', None, u'M117', None, set([u'tag1', u'tag2', u'tag3']))]

	Arguments:
	    command (unicode or Command or None): The command for which the handler result was
	        generated
	    command_type (unicode or None): The command type for which the handler
	        result was generated
	    gcode (unicode or None): The GCODE for which the handler result was
	        generated
	    subcode (unicode or None): The GCODE subcode for which the handler result
	        was generated
	    tags (set of unicode or None): The tags associated with the GCODE for which
	        the handler result was generated
	    handler_results: The handler result(s) to normalized. Can be either
	        a single result entry or a list of result entries.
	    tags_to_add (set of unicode or None): List of tags to add to expanded result
	        entries

	Returns:
	    (list) - A list of normalized handler result entries, which are
	        5-tuples consisting of ``command``, ``command_type``, ``gcode``
	        ``subcode`` and ``tags``, the latter three of which may be ``None``.
	"""

	original = command

	if handler_results is None:
		# handler didn't return anything, we'll just continue
		return [original]

	if not isinstance(handler_results, list):
		handler_results = [handler_results,]

	result = []
	for handler_result in handler_results:
		# we iterate over all handler result entries and process each one
		# individually here

		if handler_result is None:
			# entry is None, we'll ignore that entry and continue
			continue

		if command.tags:
			# copy the tags
			tags = set(command.tags)

		def expand_tags(tags, tags_to_add):
			tags = tags.copy()
			if tags_to_add and isinstance(tags_to_add, set):
				tags |= tags_to_add
			return tags

		if isinstance(handler_result, basestring):
			# entry is just a string, replace command with it
			if handler_result != original.line:
				# command changed, swap it
				command = Command.from_line(handler_result, type=original.type, tags=expand_tags(original.tags, tags_to_add))
			result.append(command)

		elif isinstance(handler_result, Command):
			if handler_result != original:
				command = copy.copy(handler_result)
				command.tags = expand_tags(original.tags, tags_to_add)
			result.append(command)

		elif isinstance(handler_result, tuple):
			# entry is a tuple, extract command and command_type
			hook_result_length = len(handler_result)

			command_type = original.type
			command_tags = original.tags

			if hook_result_length == 1:
				# handler returned just the command
				command_line, = handler_result
			elif hook_result_length == 2:
				# handler returned command and command_type
				command_line, command_type = handler_result
			elif hook_result_length == 3:
				# handler returned command, command type and additional tags
				command_line, command_type, command_tags = handler_result
			else:
				# handler returned a tuple of an unexpected length, ignore
				# and continue
				continue

			if command_line is None:
				# command is None, ignore it and continue
				continue

			if command_line != original.line or command_type != original.type:
				# command or command_type changed, tags need to be rewritten
				command_tags = expand_tags(command_tags, tags_to_add)

			result.append(Command.from_line(command_line, type=command_type, tags=command_tags))

		# reset to original
		command, command_type, gcode, subcode, tags = original

	return result

class TypedQueue(Queue):

	def __init__(self, maxsize=0):
		Queue.__init__(self, maxsize=maxsize)
		self._lookup = set()

	def put(self, item, item_type=None, *args, **kwargs):
		Queue.put(self, (item, item_type), *args, **kwargs)

	def get(self, *args, **kwargs):
		item, _ = Queue.get(self, *args, **kwargs)
		return item

	def _put(self, item):
		_, item_type = item
		if item_type is not None:
			if item_type in self._lookup:
				raise TypeAlreadyInQueue(item_type, "Type {} is already in queue".format(item_type))
			else:
				self._lookup.add(item_type)

		Queue._put(self, item)

	def _get(self):
		item = Queue._get(self)
		_, item_type = item

		if item_type is not None:
			self._lookup.discard(item_type)

		return item


class TypeAlreadyInQueue(Exception):
	def __init__(self, t, *args, **kwargs):
		Exception.__init__(self, *args, **kwargs)
		self.type = t