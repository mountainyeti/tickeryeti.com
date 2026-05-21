document.getElementById('ticker').addEventListener('submit', function(e) {
    e.preventDefault();
    var ticker = document.getElementById('tickersymbol').value.trim().toUpperCase();
    if (!ticker) return;

    var sites = [
        { id: 'yahoocheck_tickeryeti',        url: 'https://finance.yahoo.com/quote/' + ticker },
        { id: 'seekingalphacheck_tickeryeti',  url: 'https://seekingalpha.com/symbol/' + ticker + '/earnings' },
        { id: 'seccheck_tickeryeti',           url: 'https://www.sec.gov/cgi-bin/browse-edgar?CIK=' + ticker + '&owner=exclude&action=getcompany' },
        { id: 'finvizcheck_tickeryeti',        url: 'https://finviz.com/quote.ashx?t=' + ticker },
        { id: 'stanfordcheck_tickeryeti',      url: 'https://securities.stanford.edu/filings.html' },
    ];

    sites.forEach(function(site) {
        if (document.getElementById(site.id).checked) {
            window.open(site.url, '_blank');
        }
    });
});
