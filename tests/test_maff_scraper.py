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

    initial_search_page = """
    <html><body>
      <form action="./apCMM110.aspx?MOSS=1" method="post">
        <input type="hidden" name="__VIEWSTATE" value="state1" />
        <input type="hidden" name="__EVENTVALIDATION" value="ev1" />
        <input type="hidden" name="__EVENTTARGET" value="" />
        <input type="hidden" name="__EVENTARGUMENT" value="" />
        <input type="text" name="txtShuruiJFskFsh" value="" />
        <input type="submit" name="btnSearch" value="検索" />
      </form>
    </body></html>
    """
    listing_page_1 = """
    <html><body>
      <form action="./apCMM110.aspx?MOSS=1" method="post">
        <input type="hidden" name="__VIEWSTATE" value="state2" />
        <input type="hidden" name="__EVENTVALIDATION" value="ev2" />
        <input type="hidden" name="__EVENTTARGET" value="" />
        <input type="hidden" name="__EVENTARGUMENT" value="" />
      </form>
      <span id="lblKensu">2</span>
      <table id="gvwCMM110JFskFsh">
        <tr>
          <td colspan="13">
            <a href="javascript:__doPostBack('gvwCMM110JFskFsh','Page$Next')">次へ</a>
          </td>
        </tr>
        <tr>
          <th>登録番号</th><th>出願番号</th><th>農林水産植物の種類</th><th>品種名称</th>
        </tr>
        <tr>
          <td>12345</td>
          <td><a href="apCMM112.aspx?TOUROKU_NO=12345&amp;LANGUAGE=Japanese">第A-999号</a></td>
          <td>Fragaria L.</td>
          <td>とちおとめ（フリガナ：ﾄﾁｵﾄﾒ）</td>
        </tr>
        <tr>
          <td>99999</td>
          <td><a href="apCMM112.aspx?TOUROKU_NO=99999&amp;LANGUAGE=Japanese">第X-000号</a></td>
          <td>Nelumbo nucifera Gaertn.</td>
          <td>れんこん品種</td>
        </tr>
      </table>
    </body></html>
    """
    listing_page_2 = """
    <html><body>
      <form action="./apCMM110.aspx?MOSS=1" method="post">
        <input type="hidden" name="__VIEWSTATE" value="state3" />
        <input type="hidden" name="__EVENTVALIDATION" value="ev3" />
        <input type="hidden" name="__EVENTTARGET" value="" />
        <input type="hidden" name="__EVENTARGUMENT" value="" />
      </form>
      <table id="gvwCMM110JFskFsh">
        <tr><th>登録番号</th><th>出願番号</th><th>農林水産植物の種類</th><th>品種名称</th></tr>
      </table>
    </body></html>
    """
    detail_page = """
    <html><body>
      <table>
        <tr><td>登録番号</td><td>12345</td></tr>
        <tr><td>登録年月日</td><td>2020年1月2日</td></tr>
        <tr><td>出願番号</td><td>第A-999号</td></tr>
        <tr><td>出願年月日</td><td>2018/03/04</td></tr>
        <tr><td>出願公表の年月日</td><td>2019/05/06</td></tr>
        <tr><td>登録品種の名称</td><td>とちおとめ（フリガナ：ﾄﾁｵﾄﾒ）</td></tr>
        <tr><td>育成地</td><td>栃木県宇都宮市</td></tr>
        <tr><td>品種登録者の名称</td><td>栃木県</td></tr>
        <tr><td>出願者の氏名又は名称</td><td>栃木県</td></tr>
        <tr><td>育成者権の存続期間</td><td>25年</td></tr>
        <tr><td>輸出する行為の制限</td><td>無</td></tr>
        <tr><td>指定国</td><td>無</td></tr>
        <tr><td>生産する行為の制限</td><td>北海道</td></tr>
        <tr><td>指定地域</td><td>北海道</td></tr>
        <tr><td>備考</td><td>なし</td></tr>
      </table>
      <span id="lblJgakumeiName">Fragaria L.</span>
      <span id="lblJshuruiName">イチゴ属</span>
      <span id="lblShtgaiyo">果実は大果で甘味が強い。</span>
      <img src="file_library/10000/999/999_1_1.jpg" />
    </body></html>
    """

    def fake_get(url: str, params: dict | None = None) -> _FakeResponse:
        if "apCMM110.aspx" in url:
            return _FakeResponse(initial_search_page)
        if "apCMM112.aspx" in url:
            if "TOUROKU_NO=99999" in url:
                raise AssertionError("Non-Fragaria row should be filtered before detail fetch")
            return _FakeResponse(detail_page)
        raise AssertionError(f"Unexpected URL: {url} params={params}")

    post_calls: list[dict[str, str]] = []

    def fake_post(url: str, data: dict | None = None) -> _FakeResponse:
        assert data is not None
        post_calls.append(data)
        if data.get("btnSearch") == "検索":
            return _FakeResponse(listing_page_1)
        if data.get("__EVENTTARGET") == "gvwCMM110JFskFsh" and data.get("__EVENTARGUMENT") == "Page$Next":
            return _FakeResponse(listing_page_2)
        raise AssertionError(f"Unexpected POST payload: {data}")

    scraper._get = fake_get  # type: ignore[method-assign]
    scraper._post = fake_post  # type: ignore[method-assign]
    varieties = scraper.fetch_varieties()
    assert len(post_calls) == 2
    assert post_calls[0]["txtShuruiJFskFsh"] == "Fragaria L."
    assert len(varieties) == 1
    row = varieties[0]
    assert row["registration_number"] == "12345"
    assert row["name"] == "とちおとめ"
    assert row["registration_date"] == "2020-01-02"
    assert row["application_date"] == "2018-03-04"
    assert row["publication_date"] == "2019-05-06"
    assert row["scientific_name"] == "Fragaria L."
    assert row["japanese_name"] == "イチゴ属"
    assert row["breeding_place"] == "栃木県宇都宮市"
    assert row["usage_conditions"] is not None
    assert "生産する行為の制限: 北海道" in row["usage_conditions"]
    assert row["detail_image_urls"] == [
        "https://www.hinshu2.maff.go.jp/vips/cmm/file_library/10000/999/999_1_1.jpg"
    ]
