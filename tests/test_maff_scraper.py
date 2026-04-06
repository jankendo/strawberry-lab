from scraper.config import SourceConfig
from scraper.sources.maff_scraper import MaffScraper


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text


def test_fetch_varieties_parses_listing_and_detail() -> None:
    source = SourceConfig(
        source_key="maff",
        source_name="MAFF Variety Registry",
        enabled=True,
        search_url="https://www.hinshu2.maff.go.jp/vips/cmm/apCMM110.aspx?MOSS=1",
        min_interval_seconds=0,
        max_pages_per_run=3,
    )
    scraper = MaffScraper(source)

    listing_page_1 = """
    <html><body>
      <table>
        <tr>
          <th>登録番号</th><th>品種名</th>
        </tr>
        <tr>
          <td><a href="/vips/cmm/apCMM112.aspx?TOUROKU_NO=12345&LANGUAGE=Japanese">12345</a></td>
          <td>とちおとめ</td>
        </tr>
      </table>
    </body></html>
    """
    listing_page_2 = "<html><body><table></table></body></html>"
    detail_page = """
    <html><body>
      <table>
        <tr><th>登録番号</th><td>12345</td></tr>
        <tr><th>登録年月日</th><td>2020年1月2日</td></tr>
        <tr><th>出願番号</th><td>第A-999号</td></tr>
        <tr><th>出願年月日</th><td>2018/03/04</td></tr>
        <tr><th>出願公表年月日</th><td>2019/05/06</td></tr>
        <tr><th>登録品種の名称</th><td>とちおとめ</td></tr>
        <tr><th>学名</th><td>Fragaria L.</td></tr>
        <tr><th>和名</th><td>イチゴ</td></tr>
        <tr><th>育成者権者</th><td>栃木県</td></tr>
        <tr><th>出願者</th><td>栃木県</td></tr>
        <tr><th>育成地</th><td>栃木県宇都宮市</td></tr>
        <tr><th>登録品種の特性の概要</th><td>果実は大果で甘味が強い。</td></tr>
        <tr><th>育成者権の存続期間</th><td>25年</td></tr>
        <tr><th>登録品種の利用条件</th><td>特になし</td></tr>
        <tr><th>備考</th><td>なし</td></tr>
      </table>
    </body></html>
    """

    def fake_get(url: str, params: dict | None = None) -> _FakeResponse:
        if "apCMM110.aspx" in url and params and params.get("PAGE_NO") == "1":
            return _FakeResponse(listing_page_1)
        if "apCMM110.aspx" in url and params and params.get("PAGE_NO") == "2":
            return _FakeResponse(listing_page_2)
        if "apCMM112.aspx" in url:
            return _FakeResponse(detail_page)
        raise AssertionError(f"Unexpected URL: {url} params={params}")

    scraper._get = fake_get  # type: ignore[method-assign]
    varieties = scraper.fetch_varieties()
    assert len(varieties) == 1
    row = varieties[0]
    assert row["registration_number"] == "12345"
    assert row["name"] == "とちおとめ"
    assert row["registration_date"] == "2020-01-02"
    assert row["application_date"] == "2018-03-04"
    assert row["publication_date"] == "2019-05-06"
    assert row["scientific_name"] == "Fragaria L."
    assert row["japanese_name"] == "イチゴ"
    assert row["breeding_place"] == "栃木県宇都宮市"
