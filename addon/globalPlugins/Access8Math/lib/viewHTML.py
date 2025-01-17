import io
import json
import os
import re
import shutil
import uuid
from zipfile import ZipFile

import addonHandler
import config

addonHandler.initTranslation()

from jinja2 import Environment, FileSystemLoader

PATH = os.path.dirname(os.path.dirname(__file__))
TEMPLATES_PATH = os.path.join(PATH, 'web', 'templates')
env = Environment(
	loader=FileSystemLoader(TEMPLATES_PATH),
	variable_start_string='{|{',
	variable_end_string='}|}'
)

import html5lib
import markdown2
import xml.etree.ElementTree as etree

from command.action import batch


class Access8MathDocument:
	def __init__(self, path=None, exist=True):
		# path: folder/txt/zip
		self.temp = False
		if path and not os.path.exists(path):
			if not exist:
				raise OSError("path {} not exist".format(path))
			else:
				with open(path, 'w', encoding='utf8') as f:
					f.write("")
		if not path:
			path = os.path.join(PATH, 'web', 'workspace', str(uuid.uuid4()))
			self.temp = True
			os.makedirs(path)
			raw_entry = os.path.join(path, '{}.txt'.format(_("New document")))
			review_entry = os.path.join(path, '{}.html'.format(_("New document")))
			with open(raw_entry, 'w', encoding='utf8') as f:
				f.write("")
			metadata_file = os.path.join(path, 'Access8Math.json')
			metadata = {
				"raw_entry": os.path.basename(raw_entry),
				"review_entry": os.path.basename(review_entry),
			}
			dst = os.path.join(path, 'Access8Math.json')
			with open(dst, 'w', encoding='utf8') as f:
				json.dump(metadata, f)

		if os.path.isdir(path):
			self._raw_folder = path
			metadata_file = os.path.join(path, 'Access8Math.json')
			metadata = json.load(open(metadata_file))
			self.raw_entry = os.path.join(path, metadata["raw_entry"])
		elif os.path.isfile(path):
			file = os.path.basename(path)
			ext = file.split('.')[-1]
			if ext == 'zip':
				self._raw_folder = os.path.join(PATH, 'web', 'workspace', str(uuid.uuid4()))
				self.temp = True
				if not os.path.exists(self.raw_folder):
					os.makedirs(self.raw_folder)
				with ZipFile(path, 'r') as file:
					file.extractall(self.raw_folder)
				metadata_file = os.path.join(self.raw_folder, 'Access8Math.json')
				metadata = json.load(open(metadata_file))
				self.raw_entry = os.path.join(self.raw_folder, metadata["raw_entry"])
			else:
				self._raw_folder = os.path.dirname(path)
				self.raw_entry = path

		self.review_folder = os.path.join(PATH, 'web', 'workspace', 'review')

	def __del__(self):
		if self.temp:
			try:
				shutil.rmtree(self.raw_folder)
			except BaseException:
				pass

	@property
	def raw_folder(self):
		return self._raw_folder

	@raw_folder.setter
	def raw_folder(self, path):
		raw_folder = self.raw_folder
		review_folder = path
		resources = self.resources
		for resource in resources:
			try:
				dir = os.path.dirname(os.path.join(review_folder, resource))
				if not os.path.exists(dir):
					os.makedirs(dir)
				shutil.copyfile(
					os.path.join(raw_folder, resource),
					os.path.join(review_folder, resource),
				)
			except BaseException:
				pass

		self._raw_folder = path
		self.temp = False

	@property
	def review_entry(self):
		try:
			name = '.'.join(os.path.basename(self.raw_entry).split('.')[:-1])
		except BaseException:
			name = 'index'
		return os.path.join(self.review_folder, "{}.html".format(name))

	@property
	def resources(self):
		with io.open(self.raw_entry, 'r', encoding='utf8') as f:
			content = f.read()
		contentmd = markdown2.markdown(content)

		tb = html5lib.getTreeBuilder("etree", implementation=etree)
		p = html5lib.HTMLParser(tb)
		try:
			contentxml = p.parse(contentmd)
		except BaseException:
			contentxml = None

		resources = []
		if contentxml:
			for item in contentxml.iter('{http://www.w3.org/1999/xhtml}a'):
				resource = '\\'.join(item.attrib['href'].split('/'))
				resources.append(resource)
			for item in contentxml.iter('{http://www.w3.org/1999/xhtml}img'):
				resource = '\\'.join(item.attrib['src'].split('/'))
				resources.append(resource)

		return resources

	def raw2review(self):
		print(self.raw_folder)
		rawIntoReview(self.raw_folder, self.review_folder, self.resources)

		shutil.copyfile(
			os.path.join(self.raw_folder, os.path.basename(self.raw_entry)),
			os.path.join(self.review_folder, os.path.basename(self.raw_entry)),
		)

		template_folder = os.path.join(PATH, 'web', 'templates')
		shutil.copytree(
			os.path.join(template_folder, 'modules'),
			os.path.join(self.review_folder, 'modules')
		)

		metadata = {
			"raw_entry": os.path.basename(self.raw_entry),
			"review_entry": os.path.basename(self.review_entry),
		}
		dst = os.path.join(self.review_folder, 'Access8Math.json')
		with open(dst, 'w', encoding='utf8') as f:
			json.dump(metadata, f)

		for dirPath, dirNames, fileNames in os.walk(self.review_folder):
			for item in fileNames:
				item = os.path.join(dirPath, item)
				try:
					name = '.'.join(os.path.basename(item).split('.')[:-1])
					extend = os.path.basename(item).split('.')[-1]
				except BaseException:
					name = ''
					extend = ''
				if os.path.isfile(item) and extend == 'txt':
					text2template(src=item, dst=os.path.join(os.path.dirname(item), '{}.html'.format(name)))


def rawIntoReview(raw_folder, review_folder, resources):
	try:
		shutil.rmtree(review_folder)
	except BaseException:
		pass
	try:
		os.makedirs(review_folder)
	except BaseException:
		pass
	for resource in resources:
		try:
			dir = os.path.dirname(os.path.join(review_folder, resource))
			if not os.path.exists(dir):
				os.makedirs(dir)
			shutil.copyfile(
				os.path.join(raw_folder, resource),
				os.path.join(review_folder, resource),
			)
		except BaseException:
			pass


def text2template(src, dst):
	with open(src, "r", encoding="utf8") as f:
		value = f.read()
		value = batch("nemeth2latex")(value)

	try:
		title = '.'.join(os.path.basename(dst).split('.')[:-1])
	except BaseException:
		title = 'Access8Math'
	backslash_pattern = re.compile(r"\\")
	data = backslash_pattern.sub(lambda m: m.group(0).replace('\\', '\\\\'), value)
	data = data.replace(r'`', r'\`')
	# data = data.replace(r'\vec{', r'\overset{⇀}{')
	raw = data
	template = env.get_template("index.template")
	content = template.render({
		'title': title,
		'data': data,
		'raw': raw,
		'LaTeX_delimiter': config.conf["Access8Math"]["settings"]["LaTeX_delimiter"],
		'document_display': config.conf["Access8Math"]["settings"]["HTML_document_display"],
		'display': config.conf["Access8Math"]["settings"]["HTML_math_display"],
		'color': config.conf["Access8Math"]["settings"]["color"],
		'bg_color': config.conf["Access8Math"]["settings"]["bg_color"],
	})
	with open(dst, "w", encoding="utf8", newline="") as f:
		f.write(content)
	return dst
