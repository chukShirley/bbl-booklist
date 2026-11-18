import importlib.util,json,sqlite3,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('builder',ROOT/'scripts/build_catalog_db.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

class EnrichmentTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();b.DATA=Path(self.tmp.name)
  self.db=sqlite3.connect(':memory:');self.db.executescript(b.SCHEMA)
  self.db.execute("insert into books values(1,'Example','example','Author','author')")
 def tearDown(self):self.db.close();self.tmp.cleanup()
 def payload(self,**changes):
  book={'book_id':1,'title':'Example','author':'Author','isbns':['9781561454907','1561454907']};book.update(changes)
  (b.DATA/'supported-isbn-additions.json').write_text(json.dumps({'version':1,'books':[book]}))
 def test_both_isbn_forms_added(self):
  self.payload();b.apply_supported_isbns(self.db)
  self.assertEqual(self.db.execute('select count(*) from book_identifiers').fetchone()[0],2)
  self.assertEqual(self.db.execute('select count(*) from books').fetchone()[0],1)
 def test_changed_title_rejected(self):
  self.payload(title='Other')
  with self.assertRaises(AssertionError):b.apply_supported_isbns(self.db)
 def test_conflicting_isbn_rejected(self):
  self.db.execute("insert into books values(2,'Other','other','','')")
  self.db.execute("insert into book_identifiers values(2,'ISBN13','9781561454907')")
  self.payload()
  with self.assertRaises(AssertionError):b.apply_supported_isbns(self.db)
 def test_invalid_checksum_rejected(self):
  self.payload(isbns=['9781561454908'])
  with self.assertRaises(AssertionError):b.apply_supported_isbns(self.db)
 def test_existing_identifier_not_marked_new(self):
  self.db.execute("insert into book_identifiers values(1,'ISBN13','9781561454907')")
  self.payload();b.apply_supported_isbns(self.db)
  self.assertEqual(self.db.execute('select value from enrichment_identifiers').fetchall(),[('1561454907',)])

if __name__=='__main__':unittest.main()
