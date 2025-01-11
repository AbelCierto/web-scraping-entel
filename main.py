import asyncio
import csv
from playwright.async_api import async_playwright
import datetime

async def extract_links_from_page(page):
    """Extrae los enlaces de los artículos en la página actual."""
    links = await page.eval_on_selector_all(
        'article.card-plp a',
        'elements => elements.map(e => e.href)'
    )
    return links

async def get_max_pages_and_links():
    """Extrae todos los enlaces de la paginación."""
    base_url = "https://miportal.entel.pe/personas/catalogo/postpago/renovacion"
    headers = {
        "referer": "https://miportal.entel.pe/personas/producto/equipos/prod640038?poId=PO_BSC_EQP_29347&modalidad=Renovacion&planId=PO_POS_OO_24428&oferta=regular&cuota=0&flow=equipos",
        "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_extra_http_headers(headers)
        await page.goto(base_url, timeout=100000)

        await page.wait_for_selector(
            '.pagination-block__numbers .action-triggerer',
            state='visible',
            timeout=10000
        )
        
        last_page_seen = None
        all_links = []

        while True:
            links = await extract_links_from_page(page)
            all_links.extend(links)

            active_page = await page.query_selector('.pagination-block__numbers .action-triggerer.active')
            current_page = await active_page.inner_text()

            if current_page == last_page_seen:
                break

            last_page_seen = current_page
            next_page_number = int(current_page) + 1
            found_next = False

            pagination_elements = await page.query_selector_all('.pagination-block__numbers .action-triggerer')
            for element in pagination_elements:
                page_num = await element.inner_text()
                if page_num == str(next_page_number):
                    await element.click()
                    await page.wait_for_timeout(2000)
                    found_next = True
                    break

            if not found_next:
                break

        await browser.close()
        return all_links

async def extract_product_data(page, url):
    """Extrae datos de un producto desde su página."""
    headers = {
        "referer": "https://miportal.entel.pe/personas/producto/equipos/prod640038?poId=PO_BSC_EQP_29347&modalidad=Renovacion&planId=PO_POS_OO_24428&oferta=regular&cuota=0&flow=equipos",
        "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    }
    await page.set_extra_http_headers(headers)
    await page.goto(url, timeout=100000)
    
    no_stock = await page.query_selector('.noStock-container')
    if no_stock:
        print(f"Producto no disponible en: {url}")
        return {"link": url, "marca": "N/A", "modelo": "N/A", "precio_renovacion": "N/A", "precio_liberado": "N/A", "caracteristicas": "N/A"}
    
    try:
        marca = await page.eval_on_selector('.equipment-brand', 'el => el.innerText')
    except:
        marca = ""
    
    try:
        modelo = await page.eval_on_selector('.equipment-title', 'el => el.innerText')
    except:
        modelo = ""

    try:
        renovacion_element = await page.query_selector('.container-tab.active .container-price .select-title:has-text("Renovación") + .selected-price')
        if renovacion_element:
            precio_renovacion = await renovacion_element.inner_text()
            precio_renovacion = precio_renovacion.split("S/")[-1]
        else:
            precio_renovacion = "N/A"
    except:
        precio_renovacion = "N/A"
    
    try:
        liberado_element = await page.query_selector('.container-tab:not(.active) .container-price .select-title:has-text("Equipo Liberado") + .selected-price')
        if liberado_element:
            precio_liberado = await liberado_element.inner_text()
        else:
            precio_liberado = "N/A"
    except:
        precio_liberado = "N/A"
    
    caracteristicas = []
    try:
        features = await page.query_selector_all('.main-features__list .main-features__item')
        for feature in features:
            name = await feature.eval_on_selector('.component-name', 'el => el.innerText')
            value = await feature.eval_on_selector('span:last-child', 'el => el.innerText')
            caracteristicas.append(f"{name}: {value}")
    except:
        caracteristicas = []

    return {
        "link": url,
        "marca": marca,
        "modelo": modelo,
        "precio_renovacion": f"S/{precio_renovacion}",
        "precio_liberado": precio_liberado,
        "caracteristicas": ", ".join(caracteristicas)
    }


async def worker(worker_id, urls, output):
    """Worker que procesa una lista de URLs."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        while urls:
            url = urls.pop(0)
            print(f"Worker {worker_id} procesando: {url}")
            try:
                data = await extract_product_data(page, url)
                if data:
                    output.append(data)
            except Exception as e:
                print(f"Error procesando {url}: {e}")
        
        await browser.close()

async def main():
    all_links = await get_max_pages_and_links()
    print(f"Total de enlaces extraídos: {len(all_links)}")

    output = []
    workers = 4
    tasks = [worker(i, all_links, output) for i in range(workers)]
    await asyncio.gather(*tasks)
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    filename = f'productos_entel_{timestamp}.csv'

    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ["link", "marca", "modelo", "precio_renovacion", "precio_liberado", "caracteristicas"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        writer.writerows(output)

    print(f"Datos guardados en '{filename}'")

asyncio.run(main())

