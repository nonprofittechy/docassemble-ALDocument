from docassemble.base.util import DADict, DAList, DAObject, DAFile, DAFileCollection, DAFileList, defined, value, pdf_concatenate, DAOrderedDict

class ALAddendumField(DAObject):
  """
  Object representing a single field and its attributes as related to whether
  it should be displayed in an addendum. Useful for PDF templates.
  
  Required attributes:
    - field_name->str represents the name of a docassemble variable
    - overflow_trigger->int

  Optional/planned (not implemented yet):    
    - headers->dict(attribute: display label for table)
    - field_style->"list"|"table"|"string" (optional: defaults to "string")
  """
  def init(self, *pargs, **kwargs):
    super(ALAddendumField, self).init(*pargs, **kwargs)

  def overflow_value(self):
    """
    Try to return just the portion of the variable (list-like object or string)
    that exceeds the overflow trigger. Otherwise, return empty string.
    """
    if len(self.value_if_defined()) > self.overflow_trigger:
      return self.value_if_defined()[self.overflow_trigger:]
    else:
      return ""
    
  def value(self):    
    """
    Return the full value, disregarding overflow. Could be useful in addendum
    if you want to show the whole value without making user flip back/forth between multiple
    pages.
    """
    return self.value_if_defined()
    
  def safe_value(self, overflow_message = ""):
    """
    Try to return just the portion of the variable
    that is _shorter than_ the overflow trigger. Otherwise, return empty string.
    """
    if len(self.value_if_defined()) > self.overflow_trigger:
      if isinstance(self.value_if_defined(), str):
        return self.value_if_defined()[:self.overflow_trigger] + overflow_message
      else:
        return self.value_if_defined()[:self.overflow_trigger]
    else:
      return self.value_if_defined()
      
  def value_if_defined(self):
    """
    Return the value of the field if it is defined, otherwise return an empty string.
    """
    if defined(self.field_name):
      return value(self.field_name)
    return ""
  
  def __str__(self):
    return str(self.value_if_defined())
    
  def columns(self):
    """
    Return a list of the columns in this object.
    """
    if hasattr(self, headers):
      return self.headers
    else:
      return [] # TODO

class ALAddendumFieldDict(DAOrderedDict):
  """
  Object representing a list of fields in your output document, together
  with the character limit for each field.
  
  Provides convenient methods to determine if an addendum is needed and to 
  control the display of fields so the appropriate text (overflow or safe amount)
  is displayed in each context.
  
  Adding a new entry will implicitly set the `field_name` attribute of the field.
  
  optional:
    - style: if set to "overflow_only" will only display the overflow text
  """
  def init(self, *pargs, **kwargs):
    super(ALAddendumFieldDict, self).init(*pargs, **kwargs)  
    self.object_type = ALAddendumField
    self.auto_gather=False
    if not hasattr(self, 'style'):
      self.style = 'overflow_only'
    if hasattr(self, 'data'):
      self.from_list(data)
      del self.data      
  
  def initializeObject(self, *pargs, **kwargs):
    """
    When we create a new entry implicitly, make sure we also set the .field_name
    attribute to the key name so it knows its own field_name.
    """
    the_key = pargs[0]
    super().initializeObject(*pargs, **kwargs)
    self[the_key].field_name = the_key
  
  def from_list(self, data):
    for entry in data:
      new_field = self.initializeObject(entry['field_name'], ALAddendumField)
      new_field.field_name = entry['field_name']
      new_field.overflow_trigger = entry['overflow_trigger']
      
  def defined_fields(self, style='overflow_only'):
    """
    Return a filtered list of just the defined fields.
    If the "style" is set to overflow_only, only return the overflow values.
    """
    if style == 'overflow_only':
      return [field for field in self.elements.values() if defined(field.field_name) and len(field.overflow_value())]
    else:
      return [field for field in self.elements.values() if defined(field.field_name)]
  
  def overflow(self):
    return self.defined_fields(style='overflow_only')
    
  #def defined_sections(self):
  #  if self.style == 'overflow_only':    
  #    return [section for section in self.elements if len(section.defined_fields(style=self.style))]
  
class ALDocument(DADict):
  """
  An opinionated collection of typically three attachment blocks:
  1. The final version of a document, at typical key "final"
  2. The preview version of a document, at typical key "preview"
  3. An addendum of a document, at the attribute `addendum`
  
  Each form that an interview generates will get its own ALDocument object.
  
  This should really relate to one canonical document in different states. Not multiple
  unrelated output documents that might get delivered together, except the addendum.
  
  The "addendum" attribute will typically be handled in a generic object block.
  Multiple documents can use the same addendum template, with just the case caption
  varying.
  
  Required attributes:
    - filename: name used for output PDF
    - enabled
    - has_addendum: set to False if the document never has overflow, like for a DOCX template
  
  Optional attribute:
    - addendum: an attachment block
    - overflow_fields
  
  """
  def init(self, *pargs, **kwargs):
    super(ALDocument, self).init(*pargs, **kwargs)
    self.initializeAttribute('overflow_fields',ALAddendumFieldDict)
    if not hasattr(self, 'default_overflow_message'):
      self.default_overflow_message = ''
 
  def as_pdf(self, key='final'):
    return pdf_concatenate(self.as_list(key=key), filename=self.filename)

  def as_list(self, key='final'):
    if self.has_addendum and self.has_overflow():
      return [self[key], self.addendum]
    else:
      return [self[key]]
    
  def has_overflow(self):
    return len(self.overflow()) > 0
  
  def overflow(self):
    return self.overflow_fields.overflow()
    
  def safe_value(self, field_name, overflow_message=None):
    """
    Shortcut syntax for accessing the "safe" (shorter than overflow trigger)
    value of a field that we have specified as needing an addendum.
    """
    if overflow_message is None:
      overflow_message = self.default_overflow_message
    return self.overflow_fields[field_name].safe_value(overflow_message=overflow_message)

class ALDocumentBundle(DAList):
  """
  DAList of ALDocuments or nested ALDocumentBundles.
  
  Use case: providing a list of documents in a specific order.
  Example:
    - Cover page
    - Main motion form
    - Notice of Interpreter Request
 
  E.g., you may bundle documents one way for the court, one way for the user, one way for the
  opposing party. ALDocuments can separately be "enabled" or "disabled" for a particular run, which
  will affect their inclusion in all bundles.
  
  A bundle can be returned as one PDF or as a list of documents. If the list contains nested
  bundles, each nested bundle can similarly be returned as a combined PDF or a list of documents.
  
  required attributes: 
    - filename
  optional attribute: enabled
  """
  def init(self, *pargs, **kwargs):
    super(ALDocumentBundle, self).init(*pargs, **kwargs)
    self.auto_gather=False
    self.gathered=True
    # self.initializeAttribute('templates', ALBundleList)
    
  def as_pdf(self, key='final'):
    return pdf_concatenate(self.as_flat_list(key=key), filename=self.filename)
  
  def preview(self):
    return self.as_pdf(key='preview')
  
  def as_flat_list(self, key='final'):
    """
    Returns the nested bundle as a single flat list.
    """
    # Iterate through the list of self.templates
    # If this is a simple document node, check if this individual template is enabled.
    # Otherwise, call the bundle's as_list() method to show all enabled templates.
    # Unpack the list of documents at each step so this can be concatenated into a single list
    flat_list = []
    for document in self:
      if isinstance(document, ALDocumentBundle):
        flat_list.extend(document.as_list(key=key))
      elif document.enabled: # base case
        flat_list.extend(document.as_list(key=key))
                         
    return flat_list
 
  def as_pdf_list(self, key='final'):
    """
    Returns the nested bundles as a list of PDFs that is only one level deep.
    """
    return [document.as_pdf(key=key) for document in self]
  
  def as_html(self, key='final'):
    pass
    
class ALDocumentBundleDict(DADict):
  """
  A dictionary with named bundles of ALDocuments.
  In the assembly line, we expect to find two predetermined bundles:
  court_bundle and user_bundle.
  
  It may be helpful in some circumstances to have a "bundle" of bundles. E.g.,
  you may want to present the user multiple combinations of documents for
  different scenarios.
  """
  def init(self, *pargs, **kwargs):
    super(ALBundleList, self).init(*pargs, **kwargs)
    self.auto_gather=False
    self.gathered=True
    self.object_type = ALBundle
    if not hasattr(self, 'gathered'):
      self.gathered = True
    if not hasattr(self, 'auto_gather'):
      self.auto_gather=False

  def preview(format='PDF', bundle='user_bundle'):
    """
    Create a copy of the document as a single PDF that is suitable for a preview version of the 
    document (before signature is added).
    """
    return self[bundle].as_pdf(key='preview', format=format)
  
  def as_attachment(format='PDF', bundle='court_bundle'):
    """
    Return a list of PDF-ified documents, suitable to make an attachment to send_mail.
    """
    return self[bundle].as_pdf_list(key='final')