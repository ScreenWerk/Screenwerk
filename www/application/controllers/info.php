<?php

class Info extends Controller {

	function __construct() {
		parent::Controller();

		//$this->output->enable_profiler(TRUE);      

	}

	function index() {

		$this->eng();

	}

	function eng() {

		$view['page_menu_code'] = 'info';
		$view['page_content'] = $this->load->view('info/info_eng', $view, True);
		$view['box']['contact']['content'] = $this->load->view('info/contact', $view, True);
		$view['lang_link'] = anchor(site_url('/info/est'),'Eesti keeles');
		$view['box']['lang']['content'] = $this->load->view('info/language', $view, True);
		$this->load->view('main_page_view', $view);

	}

	function est() {

		$view['page_menu_code'] = 'info';
		$view['page_content'] = $this->load->view('info/info_est', $view, True);
		$view['box']['contact']['content'] = $this->load->view('info/contact', $view, True);
		$view['lang_link'] = anchor(site_url('/info'),'In English');
		$view['box']['lang']['content'] = $this->load->view('info/language', $view, True);
		$this->load->view('main_page_view', $view);

	}

	function php() {
		phpinfo();
	}

}	
	
?>
