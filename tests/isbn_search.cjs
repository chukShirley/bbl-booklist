const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'web/app.js'), 'utf8');
const funcs = source.slice(source.indexOf('function buildIsbnIndex'), source.indexOf('function bookCard'));
const books = JSON.parse(fs.readFileSync(path.join(root, 'web/catalog.json'))).books;
const ctx = vm.createContext({state:{books},normalize:v=>(v||'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim(),normalizeIsbn:v=>(v||'').toUpperCase().replace(/[^0-9X]/g,'')});
vm.runInContext(funcs, ctx);
ctx.state.isbnIndex = ctx.buildIsbnIndex(books);
let checked=0;
for (const book of books) for (const isbn of book.isbns) {
 assert(ctx.searchBooks(isbn).some(b=>b.k===book.k));checked++;
}
const sample = books.find(b=>b.isbns.length && !b.i);
const isbn = sample.isbns[0];
assert(ctx.searchBooks(isbn.slice(0,3)+'-'+isbn.slice(3)).some(b=>b.k===sample.k));
ctx.state.isbnIndex=ctx.buildIsbnIndex([{k:'legacy',i:'9781561454907'}]);
assert.equal(ctx.searchBooks('9781561454907')[0].k,'legacy');
console.log(`${checked} ISBN searches passed; legacy and hyphenated ISBN searches passed.`);
