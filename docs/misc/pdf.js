const puppeteer = require('puppeteer');
var args = process.argv.slice(2);
var url = args[0];
var pdfPath = args[1];
var title = args[2];

console.log('Saving', url, 'to', pdfPath);

// date –  formatted print date
// title – document title
// url  – document location
// pageNumber – current page number
// totalPages – total pages in the document
headerHtml = `
<div style="font-size: 10px; text-align: center; width: 100%;">
    <span>${title}</span>  
</div>`;

footerHtml = `<div style="font-size: 10px; text-align: center; width: 100%;"><span class="pageNumber"></span> / <span class="totalPages"></span></div>`;


(async() => {
    const browser = await puppeteer.launch({
        headless: true,
        executablePath: process.env.CHROME_BIN || null,
        args: ['--no-sandbox', '--headless', '--disable-gpu', '--disable-dev-shm-usage']
    });

    const page = await browser.newPage();
    await page.goto(url, { waitUntil: 'networkidle2' });
    await page.pdf({
        path: pdfPath, // path to save pdf file
        format: 'A4', // page format
        displayHeaderFooter: true, // display header and footer (in this example, required!)
        printBackground: true, // print background
        landscape: false, // use horizontal page layout
        headerTemplate: headerHtml, // indicate html template for header
        footerTemplate: footerHtml,
        scale: 1, //Scale amount must be between 0.1 and 2
        margin: { // increase margins (in this example, required!)
            top: 80,
            bottom: 80,
            left: 30,
            right: 30
        }
    });

    await browser.close();
})();